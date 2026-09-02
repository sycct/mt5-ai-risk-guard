from datetime import datetime, timedelta, timezone

import pytest

from risk_guard.ai_policy import decide_ai_call
from risk_guard.config import Settings
from risk_guard.models import RiskLevel


NOW = datetime(2026, 9, 2, 10, tzinfo=timezone.utc)


def decide(**overrides):
    values = dict(
        enabled=True,
        has_api_key=True,
        current_level=RiskLevel.WARNING,
        previous_level=RiskLevel.CAUTION,
        last_attempt_at=None,
        min_level=RiskLevel.WARNING,
        on_risk_change=True,
        cooldown_minutes=60,
        now=NOW,
    )
    values.update(overrides)
    return decide_ai_call(**values)


def test_first_high_risk_calls_ai():
    assert decide().reason == "first_high_risk"
    assert decide().should_call is True


@pytest.mark.parametrize("level", [RiskLevel.OK, RiskLevel.CAUTION])
def test_low_risk_never_calls_ai(level):
    decision = decide(current_level=level)
    assert decision.should_call is False
    assert decision.reason == "below_min_risk_level"


def test_risk_change_does_not_bypass_cooldown():
    decision = decide(last_attempt_at=NOW - timedelta(minutes=1),
                      current_level=RiskLevel.DANGER,
                      previous_level=RiskLevel.WARNING)
    assert decision.should_call is False
    assert decision.reason == "cooldown_active"


def test_risk_change_after_cooldown_calls_ai():
    decision = decide(last_attempt_at=NOW - timedelta(minutes=61),
                      current_level=RiskLevel.DANGER,
                      previous_level=RiskLevel.WARNING)
    assert decision.should_call is True
    assert decision.reason == "risk_level_changed"


def test_same_high_risk_calls_after_cooldown():
    decision = decide(last_attempt_at=NOW - timedelta(minutes=60),
                      previous_level=RiskLevel.WARNING)
    assert decision.should_call is True
    assert decision.reason == "cooldown_elapsed"


def test_settings_accept_named_minimum_level():
    settings = Settings(_env_file=None, ai_min_risk_level="danger")
    assert settings.ai_min_risk_level is RiskLevel.DANGER
