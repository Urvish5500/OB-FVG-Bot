import pandas as pd


def calculate_metrics(results: pd.DataFrame) -> dict:
    if results.empty:
        return {}

    R = results["realized_R"]
    total = len(results)
    wins = int((R > 0).sum())
    losses = int((R < 0).sum())
    scratches = int((R == 0).sum())

    win_rate = round(wins / total * 100, 1)
    total_R = round(R.sum(), 2)
    avg_R = round(R.mean(), 2)

    gross_win = R[R > 0].sum()
    gross_loss = abs(R[R < 0].sum())
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf")

    max_loss = current = 0
    for r in R:
        if r < 0:
            current += 1
            max_loss = max(max_loss, current)
        else:
            current = 0

    out = {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "breakeven": scratches,
        "win_rate_pct": win_rate,
        "total_R": total_R,
        "avg_R_per_trade": avg_R,
        "profit_factor": profit_factor,
        "max_consecutive_losses": max_loss,
    }

    # Net-of-fees metrics, using the shared fee model (strategy.levels.fee_in_R)
    if "net_R" in results.columns:
        NR = results["net_R"]
        net_gw = NR[NR > 0].sum()
        net_gl = abs(NR[NR < 0].sum())
        out.update({
            "total_fees_R": round(results["fee_R"].sum(), 2) if "fee_R" in results.columns else None,
            "total_net_R": round(NR.sum(), 2),
            "avg_net_R_per_trade": round(NR.mean(), 2),
            "net_profit_factor": round(net_gw / net_gl, 2) if net_gl > 0 else float("inf"),
        })

    return out
