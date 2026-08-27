from .models import Mt5Snapshot, RiskMetrics


def calculate_metrics(snapshot: Mt5Snapshot, ea_magic: int = 9527) -> RiskMetrics:
    buys = [p for p in snapshot.positions if p.type == "buy"]
    sells = [p for p in snapshot.positions if p.type == "sell"]
    # MT5 volume steps are decimal values; normalize binary-float artifacts before rules.
    buy_lots = round(sum(p.volume for p in buys), 8)
    sell_lots = round(sum(p.volume for p in sells), 8)
    floating = sum(p.profit for p in snapshot.positions)
    balance, equity = snapshot.account.balance, snapshot.account.equity
    dd_money = max(0.0, balance - equity) if balance is not None and equity is not None else None
    dd_percent = dd_money / balance * 100 if dd_money is not None and balance and balance > 0 else None
    buy_profit, sell_profit = sum(p.profit for p in buys), sum(p.profit for p in sells)
    worse = "neutral" if buy_profit == sell_profit else ("buy" if buy_profit < sell_profit else "sell")
    direction = "neutral" if buy_lots == sell_lots else ("long" if buy_lots > sell_lots else "short")
    ea_positions = [p for p in snapshot.positions if p.magic == ea_magic]
    ea_orders = [o for o in snapshot.pending_orders if o.magic == ea_magic]
    return RiskMetrics(
        balance=balance, equity=equity, floating_profit=floating,
        equity_drawdown_money=dd_money, equity_drawdown_percent=dd_percent,
        margin_level=snapshot.account.margin_level,
        spread=snapshot.symbol.spread if snapshot.symbol else None,
        buy_lots=buy_lots, sell_lots=sell_lots, total_lots=round(buy_lots + sell_lots, 8),
        net_lots=round(abs(buy_lots - sell_lots), 8), buy_positions_count=len(buys),
        sell_positions_count=len(sells), total_positions_count=len(snapshot.positions),
        pending_orders_count=len(snapshot.pending_orders), buy_profit=buy_profit,
        sell_profit=sell_profit, worse_side=worse, net_direction=direction,
        ea_positions_count=len(ea_positions), ea_position_lots=sum(p.volume for p in ea_positions),
        ea_pending_orders_count=len(ea_orders),
        non_ea_positions_count=len(snapshot.positions) - len(ea_positions),
        non_ea_pending_orders_count=len(snapshot.pending_orders) - len(ea_orders),
    )
