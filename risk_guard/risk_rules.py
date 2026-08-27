from dataclasses import dataclass

from .models import RiskAssessment, RiskLevel, RiskMetrics, RuleHit


@dataclass(frozen=True)
class Thresholds:
    drawdown: float
    total_lots: float
    net_lots: float
    margin_level: float


DEFAULT_THRESHOLDS = {
    RiskLevel.CAUTION: Thresholds(3, 1.0, 0.8, 2500),
    RiskLevel.WARNING: Thresholds(5, 1.5, 1.2, 2000),
    RiskLevel.DANGER: Thresholds(8, 2.0, 1.5, 1500),
    RiskLevel.EMERGENCY: Thresholds(10, 3.0, 2.0, 1000),
}

ACTIONS = {
    RiskLevel.OK: ["继续监控"],
    RiskLevel.CAUTION: ["提醒观察", "不建议提高 EA 参数"],
    RiskLevel.WARNING: ["建议停止 EA 新开仓", "建议删除挂单", "禁止继续加大 Maxlot / Totals"],
    RiskLevel.DANGER: ["建议立即停止 EA", "建议删除所有挂单", "建议考虑手动减仓"],
    RiskLevel.EMERGENCY: ["建议紧急处理", "建议优先保命，不要继续扛单"],
}


def evaluate_rules(metrics: RiskMetrics, thresholds: dict[RiskLevel, Thresholds] | None = None) -> RiskAssessment:
    table = thresholds or DEFAULT_THRESHOLDS
    hits: list[RuleHit] = []
    for level, threshold in table.items():
        checks = [
            ("equity_drawdown_percent", metrics.equity_drawdown_percent, threshold.drawdown, ">="),
            ("total_lots", metrics.total_lots, threshold.total_lots, ">="),
            ("net_lots", metrics.net_lots, threshold.net_lots, ">="),
            ("margin_level", metrics.margin_level, threshold.margin_level, "<="),
        ]
        for metric, value, limit, operator in checks:
            if value is not None and ((operator == ">=" and value >= limit) or (operator == "<=" and value <= limit)):
                hits.append(RuleHit(level=level, metric=metric, value=value, threshold=limit,
                                    message=f"{metric} {operator} {limit}"))
    level = max((h.level for h in hits), default=RiskLevel.OK)
    return RiskAssessment(level=level, metrics=metrics, hard_rule_hits=hits,
                          recommended_actions=ACTIONS[level])
