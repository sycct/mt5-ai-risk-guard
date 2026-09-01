import json

from risk_guard.deepseek_client import hard_rule_fallback
from risk_guard.models import Account, HistorySummary, Mt5Snapshot
from risk_guard.risk_engine import calculate_metrics
from risk_guard.risk_rules import evaluate_rules
from risk_guard.storage import JsonlStorage


def test_snapshot_persists_reconciliation_and_position_order_counts(tmp_path):
    snapshot = Mt5Snapshot(
        account=Account(login=123, currency="USC", balance=50000, equity=49990, profit=-10, credit=0,
                        margin=100, free_margin=49890),
        history=HistorySummary(today_closed_profit=25, today_trade_count=2),
    )
    assessment = evaluate_rules(calculate_metrics(snapshot))
    JsonlStorage(tmp_path).save_snapshot(snapshot, assessment, hard_rule_fallback(assessment))

    record = json.loads((tmp_path / "risk_snapshots.jsonl").read_text(encoding="utf-8"))
    assert record["account_profit"] == -10
    assert record["account_currency"] == "USC"
    assert record["positions_floating_profit"] == 0
    assert record["equity_balance_gap"] == -10
    assert record["reconciliation_error"] == 0
    assert record["total_positions_count"] == 0
    assert record["pending_orders_count"] == 0
    assert record["margin"] == 100
    assert record["free_margin"] == 49890
    assert record["today_closed_profit"] == 25
    assert record["today_trade_count"] == 2
