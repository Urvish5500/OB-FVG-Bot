"""Shared level logic: stop loss, opposing-box target, and risk-based sizing.

All entry/exit levels are derived from S&R boxes plus recent swings — the same
discretionary logic used when drawing trades by hand on TradingView.
"""

SWING_LOOKBACK = 20   # bars (~5h on 15m) for the recent swing-high/low reference
RISK_PCT = 0.004      # risk exactly 0.4% of equity per trade
MIN_REWARD_RR = 2.0   # only take entries where the next opposing box is >= this many R away


def is_rejection(direction: str, bar, zone) -> bool:
    """True if the bar wicked into the box and closed back out in the bias
    direction — i.e. price *rejected* the box rather than broke through it."""
    if direction == "long":
        # support: low dipped into the box, close recovered back above its top
        return bar["low"] <= zone["zone_top"] and bar["close"] > zone["zone_top"]
    # resistance: high poked into the box, close fell back below its bottom
    return bar["high"] >= zone["zone_bottom"] and bar["close"] < zone["zone_bottom"]


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


def reward_to_target(direction: str, entry: float, stop: float, zones) -> float:
    """Reward:risk to the nearest opposing box — distance(entry -> box edge)
    divided by the stop distance. 0.0 when there is no box to target. Used as
    an entry filter: only take rejections with real structural room to run."""
    risk = abs(entry - stop)
    if risk == 0:
        return 0.0
    box = find_opposing_box(direction, entry, zones)
    if box is None:
        return 0.0
    edge = box["zone_bottom"] if direction == "long" else box["zone_top"]
    reward = (edge - entry) if direction == "long" else (entry - edge)
    return reward / risk


def compute_targets(direction: str, entry: float, stop: float, zones):
    """TP1 = 2R. TP2 = fixed 3R (1:3)."""
    risk = abs(entry - stop)
    if direction == "long":
        tp1 = entry + 2 * risk
        tp2 = entry + 3 * risk
    else:
        tp1 = entry - 2 * risk
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
