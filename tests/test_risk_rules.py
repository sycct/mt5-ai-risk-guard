import pytest

from risk_guard.models import RiskLevel, RiskMetrics
from risk_guard.risk_rules import evaluate_rules


def metrics(**updates):
    values = dict(balance=50000, equity=50000, floating_profit=0, equity_drawdown_money=0,
        equity_drawdown_percent=0, margin_level=3000, spread=10, buy_lots=0, sell_lots=0,
        total_lots=0, net_lots=0, buy_positions_count=0, sell_positions_count=0,
        total_positions_count=0, pending_orders_count=0, buy_profit=0, sell_profit=0,
        worse_side="neutral", net_direction="neutral", ea_positions_count=0, ea_position_lots=0,
        ea_pending_orders_count=0, non_ea_positions_count=0, non_ea_pending_orders_count=0)
    values.update(updates)
    return RiskMetrics(**values)


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({}, RiskLevel.OK), ({"equity_drawdown_percent": 3}, RiskLevel.CAUTION),
    ({"equity_drawdown_percent": 5}, RiskLevel.WARNING), ({"equity_drawdown_percent": 8}, RiskLevel.DANGER),
    ({"equity_drawdown_percent": 10}, RiskLevel.EMERGENCY)])
def test_each_level(kwargs, expected): assert evaluate_rules(metrics(**kwargs)).level == expected


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({"total_lots": 3}, RiskLevel.EMERGENCY), ({"net_lots": 1.5}, RiskLevel.DANGER),
    ({"margin_level": 2000}, RiskLevel.WARNING), ({"equity_drawdown_percent": 3}, RiskLevel.CAUTION)])
def test_each_metric_can_trigger(kwargs, expected): assert evaluate_rules(metrics(**kwargs)).level == expected


def test_missing_critical_data_never_reports_ok():
    result = evaluate_rules(metrics(balance=None, equity=None), unavailable_reasons=["account_data"])
    assert result.level is RiskLevel.DATA_UNAVAILABLE
