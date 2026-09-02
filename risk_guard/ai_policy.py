from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import RiskLevel


@dataclass(frozen=True)
class AiCallDecision:
    should_call: bool
    reason: str


def decide_ai_call(
    *,
    enabled: bool,
    has_api_key: bool,
    current_level: RiskLevel,
    previous_level: RiskLevel | None,
    last_attempt_at: datetime | None,
    min_level: RiskLevel,
    on_risk_change: bool,
    cooldown_minutes: int,
    now: datetime,
) -> AiCallDecision:
    if not enabled:
        return AiCallDecision(False, "disabled")
    if not has_api_key:
        return AiCallDecision(False, "api_key_missing")
    if current_level is RiskLevel.DATA_UNAVAILABLE:
        return AiCallDecision(False, "data_unavailable")
    if current_level < min_level:
        return AiCallDecision(False, "below_min_risk_level")
    if last_attempt_at is None:
        return AiCallDecision(True, "first_high_risk")
    if now - last_attempt_at < timedelta(minutes=cooldown_minutes):
        return AiCallDecision(False, "cooldown_active")
    if on_risk_change and previous_level is not None and current_level != previous_level:
        return AiCallDecision(True, "risk_level_changed")
    return AiCallDecision(True, "cooldown_elapsed")
