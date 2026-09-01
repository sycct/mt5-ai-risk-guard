import json
import logging
from datetime import datetime, timezone
from typing import Any

from .mcp_client import Mt5McpClient, ToolRegistry
from .models import Account, HistorySummary, Mt5Snapshot, PendingOrder, Position, SymbolInfo

logger = logging.getLogger(__name__)


def _unwrap(raw: Any) -> Any:
    if isinstance(raw, dict) and raw.get("structuredContent") is not None:
        return raw["structuredContent"]
    if isinstance(raw, dict) and isinstance(raw.get("content"), list):
        texts = [x.get("text") for x in raw["content"] if isinstance(x, dict) and x.get("text")]
        if texts:
            try: return json.loads("\n".join(texts))
            except json.JSONDecodeError: return {"text": "\n".join(texts)}
    return raw


def _items(value: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    value = _unwrap(value)
    if isinstance(value, list): return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in keys:
            if isinstance(value.get(key), list): return value[key]
        if isinstance(value.get("result"), list): return value["result"]
    return []


def _pick(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    lowered = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name.lower() in lowered: return lowered[name.lower()]
    return default


class Mt5Adapter:
    def __init__(self, client: Mt5McpClient, symbol: str = "XAUUSD") -> None:
        self.client, self.symbol = client, symbol

    async def fetch_snapshot(self) -> Mt5Snapshot:
        tools = await self.client.list_tools()
        registry = ToolRegistry(tools)
        capabilities = {
            "account": registry.find_account_tool(), "positions": registry.find_positions_tool(),
            "orders": registry.find_orders_tool(), "symbol_info": registry.find_symbol_info_tool(),
            "history": registry.find_history_tool(),
        }
        raw: dict[str, Any] = {}
        called: dict[str, Any] = {}
        missing = [name for name, tool in capabilities.items() if not tool]
        for capability, tool in capabilities.items():
            if not tool: continue
            args = self._arguments(next(t for t in tools if t.name == tool), capability)
            try:
                if tool not in called:
                    called[tool] = _unwrap(await self.client.call_tool(tool, args))
                raw[capability] = called[tool]
            except Exception as exc:
                logger.warning("读取 MCP 能力 %s 失败: %s", capability, exc)
                missing.append(capability)
        account = self._account(raw.get("account"))
        if account.balance is None or account.equity is None:
            missing.append("account_data")
        return Mt5Snapshot(timestamp=datetime.now(timezone.utc), account=account,
                           symbol=self._symbol(raw.get("symbol_info")), positions=self._positions(raw.get("positions")),
                           pending_orders=self._orders(raw.get("orders")), history=self._history(raw.get("history")),
                           missing_capabilities=sorted(set(missing)))

    def _arguments(self, tool: Any, capability: str) -> dict[str, Any]:
        properties = tool.input_schema.get("properties", {})
        args: dict[str, Any] = {}
        for name in properties:
            lower = name.lower()
            # Account risk must include every symbol. Filtering positions, orders,
            # or history to XAUUSD can hide exposure while account profit remains
            # account-wide, producing a false empty-account result.
            if capability == "symbol_info" and "symbol" in lower:
                args[name] = self.symbol
            elif capability == "history" and lower in ("from", "date_from", "start", "start_date"):
                args[name] = datetime.now().astimezone().date().isoformat()
            elif capability == "history" and lower in ("to", "date_to", "end", "end_date"):
                args[name] = datetime.now().astimezone().isoformat()
        return args

    def _account(self, raw: Any) -> Account:
        d = raw if isinstance(raw, dict) else {}
        for key in ("account", "account_info", "data", "result"):
            if isinstance(d.get(key), dict): d = d[key]; break
        return Account(login=_pick(d, "login", "account"), server=_pick(d, "server"), balance=_pick(d, "balance"),
                       equity=_pick(d, "equity"), credit=_pick(d, "credit"), profit=_pick(d, "profit"),
                       commission=_pick(d, "commission"), margin=_pick(d, "margin"),
                       free_margin=_pick(d, "free_margin", "margin_free"),
                       margin_level=_pick(d, "margin_level", "margin_level_percent"), currency=_pick(d, "currency"))

    def _positions(self, raw: Any) -> list[Position]:
        return [Position(ticket=_pick(x, "ticket", "id"), symbol=_pick(x, "symbol"), type=_pick(x, "type", "side"),
            volume=_pick(x, "volume", "lots", default=0) or 0, open_price=_pick(x, "open_price", "price_open"),
            current_price=_pick(x, "current_price", "price_current"), profit=_pick(x, "profit", default=0) or 0,
            swap=_pick(x, "swap"), commission=_pick(x, "commission"), magic=_pick(x, "magic"),
            comment=_pick(x, "comment"), open_time=_pick(x, "open_time", "time"))
            for x in _items(raw, ("positions", "data"))]

    def _orders(self, raw: Any) -> list[PendingOrder]:
        return [PendingOrder(ticket=_pick(x, "ticket", "id"), symbol=_pick(x, "symbol"),
            type=str(_pick(x, "type", "side", default="unknown")), volume=_pick(x, "volume", "lots", "volume_initial", default=0) or 0,
            price=_pick(x, "price", "price_open"), magic=_pick(x, "magic"), comment=_pick(x, "comment"),
            create_time=_pick(x, "create_time", "time_setup", "time")) for x in _items(raw, ("orders", "pending_orders", "data"))]

    def _symbol(self, raw: Any) -> SymbolInfo | None:
        if raw is None: return None
        d = raw if isinstance(raw, dict) else {}
        items = _items(raw, ("symbols", "data"))
        if items:
            d = next((item for item in items
                      if str(_pick(item, "symbol", "name", default="")).upper() == self.symbol.upper()), items[0])
        for key in ("symbol_info", "tick", "data", "result"):
            if isinstance(d.get(key), dict): d = d[key]; break
        bid, ask = _pick(d, "bid"), _pick(d, "ask")
        point = _pick(d, "point")
        spread = _pick(d, "spread")
        if spread is None and bid is not None and ask is not None:
            spread = (ask - bid) / point if point else ask - bid
        return SymbolInfo(symbol=_pick(d, "symbol", "name", default=self.symbol), bid=bid, ask=ask, spread=spread,
                          digits=_pick(d, "digits"), point=point, volume_min=_pick(d, "volume_min"),
                          volume_step=_pick(d, "volume_step"), stops_level=_pick(d, "stops_level", "trade_stops_level"),
                          freeze_level=_pick(d, "freeze_level", "trade_freeze_level"))

    def _history(self, raw: Any) -> HistorySummary | None:
        if raw is None: return None
        d = raw if isinstance(raw, dict) else {}
        deals = _items(raw, ("deals", "positions", "orders", "history", "trades", "data"))
        profits = [float(_pick(x, "profit", default=0) or 0) for x in deals]
        return HistorySummary(today_closed_profit=_pick(d, "today_closed_profit", default=sum(profits)),
            today_gross_profit=_pick(d, "today_gross_profit", default=sum(x for x in profits if x > 0)),
            today_gross_loss=_pick(d, "today_gross_loss", default=sum(x for x in profits if x < 0)),
            today_trade_count=_pick(d, "today_trade_count", default=len(deals)))
