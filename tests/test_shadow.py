import json

from risk_guard.models import Account, Mt5Snapshot, PendingOrder, Position, RiskLevel
from risk_guard.risk_engine import calculate_metrics
from risk_guard.risk_rules import evaluate_rules
from risk_guard.shadow import evaluate_shadow_actions
from risk_guard.storage import JsonlStorage


def warning_snapshot() -> Mt5Snapshot:
    return Mt5Snapshot(
        account=Account(balance=50000, equity=49000, profit=-1000, margin_level=3000),
        positions=[
            Position(ticket=1, type="buy", volume=1.2, profit=-800, magic=9527),
            Position(ticket=2, type="sell", volume=.4, profit=-200, magic=9527),
        ],
    )


def test_warning_proposes_pause_but_never_executes_trade_action():
    snapshot = warning_snapshot()
    assessment = evaluate_rules(calculate_metrics(snapshot))
    decision = evaluate_shadow_actions(snapshot, assessment, 9527, confirmation_count=1)

    assert assessment.level is RiskLevel.WARNING
    assert [action.action for action in decision.proposed_actions] == [
        "notify_human", "pause_ea_new_entries",
    ]
    assert decision.eligible is False
    assert decision.blocked_reasons == ["confirmation_pending"]


def test_second_warning_is_marked_eligible_for_future_non_trading_policy():
    snapshot = warning_snapshot()
    assessment = evaluate_rules(calculate_metrics(snapshot))
    decision = evaluate_shadow_actions(snapshot, assessment, 9527, confirmation_count=2)

    assert decision.eligible is True
    assert decision.blocked_reasons == []


def test_data_quality_issue_blocks_all_shadow_actions():
    snapshot = warning_snapshot()
    snapshot.account.equity = 48900
    assessment = evaluate_rules(calculate_metrics(snapshot))
    decision = evaluate_shadow_actions(snapshot, assessment, 9527, confirmation_count=2)

    assert decision.proposed_actions == []
    assert decision.eligible is False
    assert "data_quality_issues" in decision.blocked_reasons


def test_danger_with_ea_pending_order_proposes_shadow_delete():
    snapshot = warning_snapshot()
    snapshot.positions[0].volume = 2.1
    snapshot.pending_orders = [PendingOrder(ticket=9, volume=.1, magic=9527)]
    assessment = evaluate_rules(calculate_metrics(snapshot))
    decision = evaluate_shadow_actions(snapshot, assessment, 9527, confirmation_count=2)

    assert assessment.level >= RiskLevel.DANGER
    assert [action.action for action in decision.proposed_actions][-1] == "delete_ea_pending_orders"
    assert decision.proposed_actions[-1].target_count == 1


def test_storage_counts_consecutive_confirmation_pending_records(tmp_path):
    snapshot = warning_snapshot()
    assessment = evaluate_rules(calculate_metrics(snapshot))
    storage = JsonlStorage(tmp_path)
    first = evaluate_shadow_actions(snapshot, assessment, 9527, confirmation_count=1)
    storage.save_shadow_decision(first)

    assert storage.consecutive_shadow_high_risk() == 1
    record = json.loads((tmp_path / "shadow_decisions.jsonl").read_text(encoding="utf-8"))
    assert record["mode"] == "shadow"
