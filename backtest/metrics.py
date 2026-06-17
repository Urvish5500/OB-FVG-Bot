import pandas as pd


def calculate_metrics(results: pd.DataFrame) -> dict:
    if results.empty:
        return {}

    wins = (results["outcome"] == "win").sum()
    losses = (results["outcome"] == "loss").sum()
    timeouts = (results["outcome"] == "timeout").sum()
    total = len(results)
    rr = results["rr_target"].iloc[0]

    win_rate = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0

    r_series = results["outcome"].map({"win": rr, "loss": -1, "timeout": -1})
    total_R = round(r_series.sum(), 2)
    avg_R = round(r_series.mean(), 2)

    gross_wins = wins * rr
    gross_losses = losses + timeouts
    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else float("inf")

    max_loss = current = 0
    for outcome in results["outcome"]:
        if outcome != "win":
            current += 1
            max_loss = max(max_loss, current)
        else:
            current = 0

    return {
        "total_trades": total,
        "wins": int(wins),
        "losses": int(losses),
        "timeouts": int(timeouts),
        "win_rate_pct": win_rate,
        "total_R": total_R,
        "avg_R_per_trade": avg_R,
        "profit_factor": profit_factor,
        "max_consecutive_losses": max_loss,
    }