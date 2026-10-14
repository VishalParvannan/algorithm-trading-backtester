"""Cost-aware FIFO matching of executions into closed trades."""
from collections import deque


def completed_trades(history):
    lots, closed = deque(), []
    for trade in history.itertuples():
        quantity = float(trade.quantity)
        if quantity > 0:
            lots.append(dict(date=trade.timestamp, price=float(trade.price), quantity=quantity, fee_per_share=float(trade.commission) / quantity))
            continue
        remaining = -quantity
        exit_fee = float(trade.commission) / remaining
        while remaining > 1e-9 and lots:
            # Match the oldest purchase first; partial exits keep the unclosed lot.
            lot = lots[0]
            matched = min(remaining, lot["quantity"])
            entry_cost = (lot["price"] + lot["fee_per_share"]) * matched
            # Fill prices already include slippage; only commissions are added here.
            proceeds = (float(trade.price) - exit_fee) * matched
            closed.append(dict(entry_date=str(lot["date"].date()), exit_date=str(trade.timestamp.date()), quantity=matched, entry_price=lot["price"], exit_price=float(trade.price), net_pnl=proceeds - entry_cost, return_pct=(proceeds / entry_cost - 1) * 100, holding_days=(trade.timestamp - lot["date"]).days, commission=(lot["fee_per_share"] + exit_fee) * matched))
            remaining -= matched
            lot["quantity"] -= matched
            if lot["quantity"] < 1e-9:
                lots.popleft()
    profits = sum(t["net_pnl"] for t in closed if t["net_pnl"] > 0)
    losses = -sum(t["net_pnl"] for t in closed if t["net_pnl"] < 0)
    return closed, dict(completed_trades=len(closed), win_rate=sum(t["net_pnl"] > 0 for t in closed) / len(closed) if closed else None, profit_factor=profits / losses if losses else None, profit_factor_no_losses=bool(profits and not losses), realized_pnl=sum(t["net_pnl"] for t in closed), average_holding_days=sum(t["holding_days"] for t in closed) / len(closed) if closed else None, open_quantity=sum(lot["quantity"] for lot in lots))
