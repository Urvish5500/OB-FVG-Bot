import pandas as pd
from data.fetcher import fetch_ohlcv
from indicators.ema import get_ema_signals
from indicators.sr_zones import detect_zones, intact_zones
from strategy.levels import (compute_stop, compute_targets, is_rejection,
                             reward_to_target, MIN_REWARD_RR)

MAX_HOLD_BARS = 200  # ~2 days on 15m before a runner is force-closed at market


def simulate_outcome(signal: dict, df: pd.DataFrame) -> dict:
    """Walk forward bar-by-bar. Book 50% at TP1 (2R), trail the rest to TP2
    with stop moved to breakeven. Returns realized R across both halves."""
    entry = signal["entry_price"]
    direction = signal["direction"]
    sl = signal["stop_loss"]
    tp1 = signal["tp1"]
    tp2 = signal["tp2"]
    risk = abs(entry - sl)
    start = signal["bar_index"] + 1

    tp1_hit = False
    stop = sl
    realized_R = 0.0
    outcome = "timeout"
    end = min(start + MAX_HOLD_BARS, len(df))

    for i in range(start, end):
        bar = df.iloc[i]
        if direction == "long":
            if bar["low"] <= stop:                       # stop checked first (worst case)
                outcome = "tp1_then_be" if tp1_hit else "loss"
                if not tp1_hit:
                    realized_R = -1.0
                break
            if not tp1_hit and bar["high"] >= tp1:
                tp1_hit = True
                realized_R += 1.0                        # 0.5 * 2R booked
                stop = entry                             # move to breakeven
            if tp1_hit and bar["high"] >= tp2:
                realized_R += 0.5 * ((tp2 - entry) / risk)
                outcome = "tp1_then_tp2"
                break
        else:  # short
            if bar["high"] >= stop:
                outcome = "tp1_then_be" if tp1_hit else "loss"
                if not tp1_hit:
                    realized_R = -1.0
                break
            if not tp1_hit and bar["low"] <= tp1:
                tp1_hit = True
                realized_R += 1.0
                stop = entry
            if tp1_hit and bar["low"] <= tp2:
                realized_R += 0.5 * ((entry - tp2) / risk)
                outcome = "tp1_then_tp2"
                break
    else:
        # window expired — close whatever remains at the last close
        last = df.iloc[end - 1]["close"]
        cur_R = (last - entry) / risk if direction == "long" else (entry - last) / risk
        if tp1_hit:
            realized_R += 0.5 * max(cur_R, 0.0)          # runner floored at breakeven
        else:
            realized_R = max(cur_R, -1.0)

    return {
        "direction": direction,
        "entry_price": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "risk": round(risk, 2),
        "bias_1d": signal["bias_1d"],
        "bias_4h": signal["bias_4h"],
        "outcome": outcome,
        "realized_R": round(realized_R, 2),
    }


def run_backtest(symbol: str = "BTC/USDT") -> pd.DataFrame:
    df_1d = get_ema_signals(fetch_ohlcv(symbol, "1d", limit=365))
    df_4h = get_ema_signals(fetch_ohlcv(symbol, "4h", limit=365 * 6))
    df_15m = fetch_ohlcv(symbol, "15m", limit=365 * 96)

    df_15m["bias_1d"] = df_1d["trend_bias"].reindex(df_15m.index, method="ffill")
    df_15m["bias_4h"] = df_4h["trend_bias"].reindex(df_15m.index, method="ffill")

    zones = detect_zones(df_15m)

    signals = []
    for i in range(len(df_15m)):
        bar = df_15m.iloc[i]
        # trade only with the trend: 1d AND 4h bias must agree on direction
        if bar["bias_1d"] == "bullish" and bar["bias_4h"] == "bullish":
            direction = "long"
        elif bar["bias_1d"] == "bearish" and bar["bias_4h"] == "bearish":
            direction = "short"
        else:
            continue

        zone_type = "support" if direction == "long" else "resistance"

        # boxes that are intact at this bar: confirmed (no lookahead) and not
        # yet closed through — persistence lets old boxes catch later retests
        zones_now = intact_zones(zones, df_15m.index[i])

        for _, zone in zones_now.iterrows():
            if zone["type"] != zone_type:
                continue
            if is_rejection(direction, bar, zone):
                entry = bar["close"]
                sl = compute_stop(direction, entry, zone, df_15m, i)
                # require real structural room to the next box, else skip the bar
                if reward_to_target(direction, entry, sl, zones_now) < MIN_REWARD_RR:
                    break
                tp1, tp2 = compute_targets(direction, entry, sl, zones_now)
                signals.append({
                    "bar_index": i,
                    "direction": direction,
                    "entry_price": entry,
                    "stop_loss": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "bias_1d": bar["bias_1d"],
                    "bias_4h": bar["bias_4h"],
                })
                break

    results = [simulate_outcome(s, df_15m) for s in signals]
    return pd.DataFrame(results) if results else pd.DataFrame()


def run_multi_backtest(symbols: list = None) -> pd.DataFrame:
    if symbols is None:
        symbols = ["BTC/USDT", "ETH/USDT"]

    all_results = []
    for symbol in symbols:
        print(f"Running backtest for {symbol}...")
        results = run_backtest(symbol)
        if not results.empty:
            results["symbol"] = symbol
            all_results.append(results)

    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
