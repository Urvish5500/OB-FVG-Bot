"""Shared level logic: stop loss, opposing-box target, and risk-based sizing.

All entry/exit levels are derived from S&R boxes plus recent swings — the same
discretionary logic used when drawing trades by hand on TradingView.
"""

SWING_LOOKBACK = 20   # bars (~5h on 15m) for the recent swing-high/low reference
RISK_PCT = 0.004      # risk exactly 0.4% of equity per trade
MIN_REWARD_RR = 2.0   # only take entries where the next opposing box is >= this many R away

# Binance USDⓈ-M fees, single source of truth shared by the backtest, the manual
# journal, and live trade closing. Limit fills (entries + resting take-profits)
# are maker; market fills (stop-outs, breakeven stops, timeouts, manual market
# exits) are taker.
TAKER_FEE = 0.0005    # 0.05% market fill
MAKER_FEE = 0.0002    # 0.02% limit fill

# Exit reasons that fill as a resting limit take-profit (maker). Anything else —
# stop-out, breakeven, timeout, manual/market close — is a taker market fill.
MAKER_EXIT_REASONS = ("tp", "tp1", "tp2", "tp_box", "tp_3r", "take_profit")


def exit_is_maker(exit_reason: str, tp_market: bool = False) -> bool:
    """Whether the exit leg fills as maker (limit TP) vs taker (market). The
    single decision point shared by the journal and live close_trade."""
    return (not tp_market) and (exit_reason in MAKER_EXIT_REASONS)


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


def fee_in_R(entry: float, stop: float, tp1: float, final_exit: float,
             hit_tp1: bool, final_is_market: bool, tp_market: bool = False) -> float:
    """Round-turn trading fees expressed in R for the blended 50%@TP1 / 50%@runner
    model. Equity/size-independent: with risk-based sizing the fee in R depends
    only on the price legs and the stop distance, so the identical number applies
    to the R-based backtest and the $-based manual journal (which multiplies by
    RISK_PCT * equity to get dollars).

    Entry (full size) and resting take-profits fill as maker. The final leg is
    taker when it is a stop-out / breakeven / timeout (final_is_market) or was
    clicked out at market (tp_market).
    """
    risk = abs(entry - stop)
    if risk == 0:
        return 0.0
    final_rate = TAKER_FEE if (final_is_market or tp_market) else MAKER_FEE
    fee = entry * MAKER_FEE                          # entry leg, full size, limit
    if hit_tp1:
        tp1_rate = TAKER_FEE if tp_market else MAKER_FEE
        fee += 0.5 * tp1 * tp1_rate + 0.5 * final_exit * final_rate
    else:
        fee += final_exit * final_rate              # whole position exits at once
    return round(fee / risk, 4)


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
