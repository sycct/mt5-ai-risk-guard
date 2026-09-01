import pytest

from risk_guard.deepseek_client import InvalidAiResponse, validate_ai_narrative
from risk_guard.models import AiRiskReport, RiskLevel


def report(summary="账户风险较低", main_risks=None, reasoning="基于硬规则和完整账户数据"):
    return AiRiskReport(
        risk_level=RiskLevel.OK,
        summary=summary,
        main_risks=main_risks or ["当前未触发硬规则风险"],
        recommended_actions=["继续监控"],
        do_not_do=["不要无限加仓"],
        reasoning_brief=reasoning,
    )


def test_qualitative_ai_narrative_is_accepted():
    validate_ai_narrative(report())


@pytest.mark.parametrize("summary", [
    "保证金比例为四万七千点", "浮亏为40.5 USC", "当前有五个持仓",
])
def test_numeric_ai_narrative_is_rejected(summary):
    with pytest.raises(InvalidAiResponse):
        validate_ai_narrative(report(summary=summary))


@pytest.mark.parametrize("action", ["建议反向对冲", "考虑加仓", "人工平仓", "适当减仓"])
def test_unapproved_trading_action_in_narrative_is_rejected(action):
    with pytest.raises(InvalidAiResponse):
        validate_ai_narrative(report(main_risks=[action]))
