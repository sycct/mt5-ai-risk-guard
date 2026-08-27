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

