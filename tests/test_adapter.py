import pytest

from risk_guard.models import ToolInfo
from risk_guard.mt5_adapter import Mt5Adapter


class FakeClient:
    def __init__(self):
        self.calls = []
        self.tools = [
            ToolInfo(name="get_trading_account_info", inputSchema={"type": "object"}),
            ToolInfo(name="get_trading_open_positions", inputSchema={"type": "object"}),
            ToolInfo(name="get_marketwatch_symbols", inputSchema={"type": "object", "properties": {"symbol": {"type": "string"}}}),
            ToolInfo(name="get_trading_history_positions", inputSchema={"type": "object"}),
        ]

    async def list_tools(self):
        return self.tools

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        return {
            "get_trading_account_info": {"balance": 50000, "equity": 49000, "margin_level": 3000},
            "get_trading_open_positions": {
                "positions": [{"ticket": 1, "symbol": "XAUUSD", "type": 0, "volume": 0.2, "profit": -5}],
                "orders": [{"ticket": 2, "symbol": "XAUUSD", "type": "buy_limit", "volume": 0.1}],
            },
            "get_marketwatch_symbols": {"symbols": [{"name": "XAUUSD", "bid": 2500, "ask": 2500.2, "point": 0.01}]},
            "get_trading_history_positions": {"positions": [{"profit": 12}]},
        }[name]


@pytest.mark.asyncio
async def test_combined_positions_and_orders_tool_is_called_once_and_split():
    client = FakeClient()
    snapshot = await Mt5Adapter(client).fetch_snapshot()

    assert snapshot.account.balance == 50000
    assert len(snapshot.positions) == 1
    assert len(snapshot.pending_orders) == 1
    assert client.calls.count("get_trading_open_positions") == 1
    assert snapshot.symbol and snapshot.symbol.symbol == "XAUUSD"
    assert snapshot.missing_capabilities == []
