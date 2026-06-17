"""Live (paper) position management.

Walks each open trade forward on the latest *closed* 15m bar, mirroring
backtest.engine.simulate_outcome: book 50% at TP1, move the stop to breakeven,
run the runner to TP2, force-close on timeout — finalising with the blended net
(fees included) via database.db.close_trade. This is what turns the bot from a
signal logger into an actual paper trader.

The decision is split into a pure `_decide()` (no I/O, easy to test) and an
`_apply()` that talks to the DB.
"""
from datetime import datetime, timedelta

from data.fetcher import fetch_ohlcv
from database.db import get_open_trades, close_trade, mark_tp1_filled

MAX_HOLD = timedelta(minutes=200 * 15)   # ~2 days, matches backtest MAX_HOLD_BARS


def _to_ccxt_symbol(sym: str) -> str:
    """'BTCUSDT' -> 'BTC/USDT' for the fetcher; pass through if already slashed."""
    if "/" in sym:
        return sym
    return sym[:-4] + "/" + sym[-4:] if sym.endswith("USDT") else sym


def _closed_bar(ccxt_symbol: str):
    """Most recent *fully closed* 15m bar. The last row is the still-forming
    candle, so the just-closed bar is the second-to-last."""
    df = fetch_ohlcv(ccxt_symbol, "15m", limit=3)
    if len(df) < 2:
        return None
    return df.iloc[-2]


def _decide(trade: dict, bar, now: datetime):
    """Pure decision for one open trade against one closed bar. Returns an action
    dict or None (still open). Mirrors simulate_outcome: stop checked first
    (worst case), then TP1 (book half + stop to BE), then TP2, then timeout.

    Actions:
      {"action": "book_tp1"}  — TP1 filled this bar, runner stays open
      {"action": "close", "price", "hit_tp1", "reason", "market", "note"}
    """
    direction = trade["direction"]
    entry, sl = trade["entry_price"], trade["stop_loss"]
    tp1, tp2 = trade["take_profit_1"], trade["take_profit_2"]
    tp1_filled = bool(trade["tp1_filled"])
    high, low, close = bar["high"], bar["low"], bar["close"]
    working_stop = entry if tp1_filled else sl

    if direction == "long":
        stop_hit = low <= working_stop
        tp1_hit = high >= tp1
        tp2_hit = high >= tp2
    else:  # short
        stop_hit = high >= working_stop
        tp1_hit = low <= tp1
        tp2_hit = low <= tp2

    # 1) stop first — worst case within the bar
    if stop_hit:
        if tp1_filled:
            return {"action": "close", "price": entry, "hit_tp1": True,
                    "reason": "breakeven", "market": True,
                    "note": "runner stopped at breakeven"}
        return {"action": "close", "price": sl, "hit_tp1": False,
                "reason": "sl", "market": True, "note": "stopped out before TP1"}

    # 2) TP1 fills this bar -> book half, move stop to BE (maybe TP2 same bar)
    if not tp1_filled and tp1_hit:
        if tp2_hit:
            return {"action": "close", "price": tp2, "hit_tp1": True,
                    "reason": "tp_3r", "market": False, "note": "TP1 then TP2 same bar"}
        return {"action": "book_tp1"}

    # 3) runner reaches TP2 (TP1 booked on an earlier bar)
    if tp1_filled and tp2_hit:
        return {"action": "close", "price": tp2, "hit_tp1": True,
                "reason": "tp_3r", "market": False, "note": "runner hit TP2"}

    # 4) timeout -> close whatever remains at market
    if now - trade["entry_time"] > MAX_HOLD:
        return {"action": "close", "price": close, "hit_tp1": tp1_filled,
                "reason": "timeout", "market": True, "note": "held past max duration"}

    return None


def _apply(trade: dict, action: dict):
    if action["action"] == "book_tp1":
        mark_tp1_filled(trade["id"])
        print(f"  ✓ {trade['symbol']} #{trade['id']} TP1 filled — booked 50%, stop → breakeven")
    else:
        close_trade(trade["id"], action["price"], action["hit_tp1"],
                    action["reason"], final_is_market=action["market"],
                    notes=action["note"])


def manage_open_trades(now: datetime = None):
    """Advance every open trade by one closed 15m bar. Called each 15m tick."""
    now = now or datetime.now()
    open_trades = get_open_trades()
    if not open_trades:
        return

    bars = {}  # cache one fetch per symbol
    for trade in open_trades:
        sym = trade["symbol"]
        if sym not in bars:
            bars[sym] = _closed_bar(_to_ccxt_symbol(sym))
        bar = bars[sym]
        if bar is None:
            continue
        action = _decide(trade, bar, now)
        if action:
            _apply(trade, action)
