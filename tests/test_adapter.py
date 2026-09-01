import pytest

from risk_guard.models import ToolInfo
from risk_guard.mt5_adapter import Mt5Adapter


class FakeClient:
    def __init__(self):
        self.calls = []
        self.arguments = {}
        self.tools = [
            ToolInfo(name="get_trading_account_info", inputSchema={"type": "object"}),
            ToolInfo(name="get_trading_open_positions", inputSchema={"type": "object", "properties": {"symbol": {"type": "string"}}}),
            ToolInfo(name="get_marketwatch_symbols", inputSchema={"type": "object", "properties": {"symbol": {"type": "string"}}}),
            ToolInfo(name="get_trading_history_positions", inputSchema={"type": "object", "properties": {
                "symbol": {"type": "string"}, "datetime_from": {"type": "string"}, "datetime_to": {"type": "string"}}}),
        ]

    async def list_tools(self):
        return self.tools

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        self.arguments[name] = arguments
        return {
            "get_trading_account_info": {"account": {"balance": 50000, "equity": 49000, "credit": 100,
                                         "profit": -1100, "commissions": -2, "margin": 100}},
            "get_trading_open_positions": {
                "positions": [{"position_id": 1, "symbol": "XAUUSD.c", "action": "buy",
                               "magic_number": 9527, "volume": 0.2, "price_last": 2500, "profit": -5}],
                "orders": [{"order_id": 2, "symbol": "XAUUSD.c", "type": "buy_limit",
                            "volume_initial": 0.1, "price_order": 2490, "magic_number": 9527}],
            },
            "get_marketwatch_symbols": {"symbols": [{"name": "XAUUSD.c", "bidPrice": 2500, "askPrice": 2500.2, "point": 0.01}]},
            "get_trading_history_positions": {"positions": [{"profit": 12}]},
        }[name]


@pytest.mark.asyncio
async def test_combined_positions_and_orders_tool_is_called_once_and_split():
    client = FakeClient()
    snapshot = await Mt5Adapter(client).fetch_snapshot()

    assert snapshot.account.balance == 50000
    assert snapshot.account.credit == 100
    assert snapshot.account.profit == -1100
    assert snapshot.account.commission == -2
    assert snapshot.account.margin_level == 49000
    assert len(snapshot.positions) == 1
    assert snapshot.positions[0].volume == .2
    assert snapshot.positions[0].type == "buy"
    assert snapshot.positions[0].magic == 9527
    assert len(snapshot.pending_orders) == 1
    assert client.calls.count("get_trading_open_positions") == 1
    assert snapshot.pending_orders[0].magic == 9527
    assert snapshot.symbol and snapshot.symbol.symbol == "XAUUSD.c"
    assert snapshot.symbol.spread == pytest.approx(20)
    assert snapshot.missing_capabilities == []
    assert client.arguments["get_marketwatch_symbols"]["symbol"] == "XAUUSD.c"


def test_only_symbol_info_is_filtered_by_symbol():
    adapter = Mt5Adapter(FakeClient(), "XAUUSD")
    tools = {item.name: item for item in adapter.client.tools}

    assert adapter._arguments(tools["get_trading_open_positions"], "positions") == {}
    assert adapter._arguments(tools["get_marketwatch_symbols"], "symbol_info") == {"symbol": "XAUUSD"}
    history_args = adapter._arguments(tools["get_trading_history_positions"], "history")
    assert "symbol" not in history_args
    assert "datetime_from" in history_args
    assert "datetime_to" in history_args


@pytest.mark.asyncio
async def test_unparsed_position_volume_and_margin_are_marked_missing():
    class IncompleteClient(FakeClient):
        async def call_tool(self, name, arguments):
            if name == "get_trading_account_info":
                return {"balance": 50000, "equity": 49999, "profit": -1}
            if name == "get_trading_open_positions":
                return {"positions": [{"ticket": 1, "type": 0, "profit": -1}]}
            return await super().call_tool(name, arguments)

    snapshot = await Mt5Adapter(IncompleteClient()).fetch_snapshot()
    assert "positions_volume_data" in snapshot.missing_capabilities
    assert "margin_level_data" in snapshot.missing_capabilities
