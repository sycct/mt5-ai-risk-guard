import json
import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import ResourceInfo, ToolInfo

logger = logging.getLogger(__name__)


class McpError(RuntimeError):
    pass


class Mt5McpClient:
    """Minimal MCP Streamable HTTP client; no MT5-specific tool names are assumed."""

    def __init__(self, url: str, headers: dict[str, str] | None = None,
                 timeout: float = 15, debug: bool = False) -> None:
        self.url, self.debug = url, debug
        self._secret_values = [v for v in (headers or {}).values() if v]
        base_headers = {"Accept": "application/json, text/event-stream", **(headers or {})}
        self._http = httpx.AsyncClient(headers=base_headers, timeout=timeout)
        self._session_id: str | None = None
        self._request_id = 0
        self.server_info: dict[str, Any] = {}

    async def __aenter__(self) -> "Mt5McpClient":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=3),
           retry=retry_if_exception_type((httpx.HTTPError, McpError)), reraise=True)
    async def _rpc(self, method: str, params: dict[str, Any] | None = None,
                   notification: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notification:
            self._request_id += 1
            payload["id"] = self._request_id
        headers = {"MCP-Protocol-Version": "2025-03-26"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        if self.debug:
            logger.debug("MCP request: %s", self._redact(json.dumps(payload, ensure_ascii=False)))
        response = await self._http.post(self.url, json=payload, headers=headers)
        response.raise_for_status()
        self._session_id = response.headers.get("mcp-session-id", self._session_id)
        if notification or response.status_code == 202 or not response.content:
            return {}
        data = self._decode_response(response)
        if "error" in data:
            raise McpError(f"MCP {method} failed: {data['error']}")
        if self.debug:
            logger.debug("MCP response: %s", self._redact(json.dumps(data, ensure_ascii=False)))
        return data.get("result", data)

    def _decode_response(self, response: httpx.Response) -> dict[str, Any]:
        if "text/event-stream" not in response.headers.get("content-type", ""):
            return response.json()
        events = []
        for line in response.text.splitlines():
            if line.startswith("data:"):
                value = line[5:].strip()
                if value:
                    events.append(json.loads(value))
        if not events:
            raise McpError("MCP returned an empty event stream")
        return events[-1]

    def _redact(self, text: str) -> str:
        for secret in self._secret_values:
            text = text.replace(secret, "***REDACTED***")
            if " " in secret:
                text = text.replace(secret.split(" ", 1)[-1], "***REDACTED***")
        return text

    async def connect(self) -> None:
        result = await self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mt5-ai-risk-guard", "version": "0.1.0"},
        })
        self.server_info = result.get("serverInfo", {})
        await self._rpc("notifications/initialized", notification=True)

    async def list_tools(self) -> list[ToolInfo]:
        result = await self._rpc("tools/list")
        return [ToolInfo.model_validate(item) for item in result.get("tools", [])]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._rpc("tools/call", {"name": name, "arguments": arguments or {}})

    async def list_resources(self) -> list[ResourceInfo]:
        result = await self._rpc("resources/list")
        return [ResourceInfo.model_validate(item) for item in result.get("resources", [])]

    async def close(self) -> None:
        await self._http.aclose()


class ToolRegistry:
    KEYWORDS = {
        "account": (("account", "balance", "equity", "margin"), ("trade", "order", "position")),
        "positions": (("position", "positions", "open trades"), ("history", "close")),
        "orders": (("pending", "orders", "order list"), ("history", "send", "delete")),
        "symbol_info": (("symbol", "quote", "tick", "market", "spread"), ("order", "trade")),
        "history": (("history", "deals", "closed", "transactions"), ("open", "send")),
    }

    def __init__(self, tools: list[ToolInfo]) -> None:
        self.tools = tools

    def _find(self, capability: str) -> str | None:
        positives, negatives = self.KEYWORDS[capability]
        best: tuple[int, str] | None = None
        for tool in self.tools:
            haystack = f"{tool.name} {tool.description} {json.dumps(tool.input_schema)}".lower()
            score = sum(3 if word in tool.name.lower() else 1 for word in positives if word in haystack)
            score -= sum(2 for word in negatives if word in haystack)
            if score > 0 and (best is None or score > best[0]):
                best = (score, tool.name)
        return best[1] if best else None

    def find_account_tool(self) -> str | None: return self._find("account")
    def find_positions_tool(self) -> str | None: return self._find("positions")
    def find_orders_tool(self) -> str | None: return self._find("orders")
    def find_symbol_info_tool(self) -> str | None: return self._find("symbol_info")
    def find_history_tool(self) -> str | None: return self._find("history")

