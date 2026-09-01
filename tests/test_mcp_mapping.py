from risk_guard.mcp_client import ToolRegistry
from risk_guard.models import ToolInfo


def tool(name: str, description: str = "") -> ToolInfo:
    return ToolInfo(name=name, description=description, inputSchema={"type": "object"})


def test_real_mt5_tools_are_mapped_without_selecting_mutations():
    registry = ToolRegistry([
        tool("get_workspace_info", "workspace metadata and community account"),
        tool("get_trading_account_info", "trading account; never places or cancels orders"),
        tool("get_trading_open_positions", "open positions and orders"),
        tool("get_marketwatch_symbols", "symbols and trading conditions"),
        tool("add_marketwatch_symbol", "changes visibility; never cancels orders"),
        tool("get_trading_history_positions", "historical positions"),
        tool("trade_send_market_order", "places a real order"),
    ])

    assert registry.find_account_tool() == "get_trading_account_info"
    assert registry.find_positions_tool() == "get_trading_open_positions"
    assert registry.find_orders_tool() == "get_trading_open_positions"
    assert registry.find_symbol_info_tool() == "get_marketwatch_symbols"
    assert registry.find_history_tool() == "get_trading_history_positions"


def test_mutating_tool_is_never_used_as_fallback_reader():
    registry = ToolRegistry([tool("add_marketwatch_symbol", "orders")])
    assert registry.find_orders_tool() is None
