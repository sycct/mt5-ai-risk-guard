from risk_guard.models import Position, ToolInfo


def test_position_parses_mt5_side_and_extra_fields():
    position = Position.model_validate({"ticket": 1, "type": 0, "volume": "0.1", "profit": "-3.5", "extra": 1})
    assert position.type == "buy"
    assert position.volume == 0.1


def test_tool_alias_input_schema():
    tool = ToolInfo.model_validate({"name": "account_info", "inputSchema": {"type": "object"}})
    assert tool.input_schema["type"] == "object"

