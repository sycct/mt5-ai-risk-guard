from risk_guard.models import Account, Mt5Snapshot, PendingOrder, Position
from risk_guard.risk_engine import calculate_metrics


def test_lot_direction_and_magic_filtering():
    snapshot = Mt5Snapshot(account=Account(balance=50000, equity=49000), positions=[
        Position(type="buy", volume=1.2, profit=-100, magic=9527),
        Position(type="sell", volume=.4, profit=20, magic=7),
    ], pending_orders=[PendingOrder(volume=.1, magic=9527), PendingOrder(volume=.2, magic=8)])
    m = calculate_metrics(snapshot)
    assert (m.buy_lots, m.sell_lots, m.total_lots, m.net_lots) == (1.2, .4, 1.6, .8)
    assert m.ea_positions_count == 1 and m.non_ea_positions_count == 1
    assert m.ea_pending_orders_count == 1 and m.worse_side == "buy"


def test_empty_positions():
    m = calculate_metrics(Mt5Snapshot(account=Account(balance=50000, equity=50000)))
    assert m.total_lots == m.net_lots == m.floating_profit == 0
    assert m.net_direction == "neutral"


def test_account_equity_reconciliation_and_profit_mismatch():
    snapshot = Mt5Snapshot(
        account=Account(balance=50000, equity=49910, credit=10, profit=-100),
        positions=[Position(type="buy", volume=.1, profit=-90)],
    )
    m = calculate_metrics(snapshot)
    assert m.equity_balance_gap == -90
    assert m.reconciliation_error == 0
    assert m.positions_floating_profit == -90
    assert m.account_profit == -100
    assert m.data_quality_issues == ["account_and_positions_profit_mismatch"]


def test_missing_account_profit_is_reported_when_equity_differs():
    m = calculate_metrics(Mt5Snapshot(account=Account(balance=50000, equity=49990)))
    assert m.reconciliation_error is None
    assert m.data_quality_issues == ["account_profit_missing_for_equity_reconciliation"]


def test_small_profit_difference_between_sequential_calls_is_tolerated():
    snapshot = Mt5Snapshot(
        account=Account(balance=50000, equity=49931.65, profit=-68.35),
        positions=[Position(type="buy", volume=.1, profit=-70.35)],
    )
    assert calculate_metrics(snapshot).data_quality_issues == []


def test_total_lots_includes_unknown_direction_for_safety():
    snapshot = Mt5Snapshot(
        account=Account(balance=50000, equity=50000),
        positions=[Position(type="unknown", volume=.2)],
    )
    m = calculate_metrics(snapshot)
    assert m.total_lots == .2
    assert m.buy_lots == m.sell_lots == 0
