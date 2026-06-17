"""Shared level logic: stop loss, opposing-box target, and risk-based sizing.

All entry/exit levels are derived from S&R boxes plus recent swings — the same
discretionary logic used when drawing trades by hand on TradingView.
"""

SWING_LOOKBACK = 20   # bars (~5h on 15m) for the recent swing-high/low reference
RISK_PCT = 0.004      # risk exactly 0.4% of equity per trade


def compute_stop(direction: str, entry: float, zone, df, bar_idx: int,
                 lookback: int = SWING_LOOKBACK) -> float:
    """Stop = the *farther* of the box edge and the recent swing high/low."""
    lo = max(0, bar_idx - lookback)
    window = df.iloc[lo:bar_idx + 1]
    if direction == "long":
        zone_edge = zone["zone_bottom"]
        swing = window["low"].min()
        return min(zone_edge, swing)        # farther = lower for a long
    zone_edge = zone["zone_top"]
    swing = window["high"].max()
    return max(zone_edge, swing)            # farther = higher for a short


def find_opposing_box(direction: str, entry: float, zones):
    """Nearest opposing S&R box beyond entry in the trade direction, or None."""
    if zones.empty:
        return None
    if direction == "long":
        # target resistance above entry; nearest = lowest zone_bottom above entry
        cands = zones[(zones["type"] == "resistance") & (zones["zone_bottom"] > entry)]
        return None if cands.empty else cands.loc[cands["zone_bottom"].idxmin()]
    # target support below entry; nearest = highest zone_top below entry
    cands = zones[(zones["type"] == "support") & (zones["zone_top"] < entry)]
    return None if cands.empty else cands.loc[cands["zone_top"].idxmax()]


def compute_targets(direction: str, entry: float, stop: float, zones):
    """TP1 = 2R. TP2 = nearest opposing box edge if beyond TP1, else 3R."""
    risk = abs(entry - stop)
    box = find_opposing_box(direction, entry, zones)
    if direction == "long":
        tp1 = entry + 2 * risk
        if box is not None and box["zone_bottom"] > tp1:
            tp2 = box["zone_bottom"]
        else:
            tp2 = entry + 3 * risk
    else:
        tp1 = entry - 2 * risk
        if box is not None and box["zone_top"] < tp1:
            tp2 = box["zone_top"]
        else:
            tp2 = entry - 3 * risk
    return tp1, tp2


def size_trade(equity: float, entry: float, stop: float,
               risk_pct: float = RISK_PCT) -> dict:
    """Risk-based sizing. Quantity is set so a stop-out loses exactly risk_pct
    of equity; leverage is whatever is needed to hold that notional (min 1x),
    matching a manual trade calculator."""
    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        return {"quantity": 0.0, "notional": 0.0, "leverage": 1.0}
    qty = (equity * risk_pct) / risk_per_unit
    notional = qty * entry
    leverage = max(1.0, notional / equity)
    return {
        "quantity": round(qty, 6),
        "notional": round(notional, 2),
        "leverage": round(leverage, 2),
    }
