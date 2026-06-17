import pandas as pd
from data.fetcher import fetch_ohlcv
from indicators.ema import get_ema_signals
from indicators.sr_zones import detect_zones
from indicators.volume_analysis import get_volume_signals


def simulate_outcome(signal: dict, df: pd.DataFrame, rr_target: float) -> dict:
    entry = signal["entry_price"]
    if signal["direction"] == "long":
        sl = signal["zone_bottom"]
        tp = entry + rr_target * (entry - sl)
    else:
        sl = signal["zone_top"]
        tp = entry - rr_target * (sl - entry)

    risk = abs(entry - sl)
    start = signal["bar_index"] + 1

    for i in range(start, min(start + 50, len(df))):
        bar = df.iloc[i]
        if signal["direction"] == "long":
            if bar["low"] <= sl:
                outcome = "loss"
                break
            if bar["high"] >= tp:
                outcome = "win"
                break
        else:
            if bar["high"] >= sl:
                outcome = "loss"
                break
            if bar["low"] <= tp:
                outcome = "win"
                break
    else:
        outcome = "timeout"

    return {
        "direction": signal["direction"],
        "entry_price": entry,
        "sl": sl,
        "tp": tp,
        "risk": round(risk, 2),
        "rr_target": rr_target,
        "bias_1d": signal["bias_1d"],
        "bias_4h": signal["bias_4h"],
        "outcome": outcome,
    }


def run_backtest(symbol: str = "BTC/USDT", rr_target: float = 2.0) -> pd.DataFrame:
    # Fetch data for all three timeframes
    df_1d = get_ema_signals(fetch_ohlcv(symbol, "1d", limit=365))
    df_4h = get_ema_signals(fetch_ohlcv(symbol, "4h", limit=365 * 6))
    df_15m = fetch_ohlcv(symbol, "15m", limit=365 * 96)

    # Add volume signals to 15m
    df_15m = get_volume_signals(df_15m)

    # Align higher timeframe biases down to 15m using forward fill
    df_15m["bias_1d"] = df_1d["trend_bias"].reindex(df_15m.index, method="ffill")
    df_15m["bias_4h"] = df_4h["trend_bias"].reindex(df_15m.index, method="ffill")

    # Detect SR zones on 15m
    zones = detect_zones(df_15m)

    # Loop through 15m bars looking for entry signals
    signals = []
    for i in range(len(df_15m)):
        bar = df_15m.iloc[i]
        bias = bar["bias_1d"] if bar["bias_1d"] == bar["bias_4h"] else None
        if bias not in ("bullish", "bearish"):
            continue
        if bar["volume_tier"] not in ("high", "very_high"):
            continue

        direction = "long" if bias == "bullish" else "short"
        zone_type = "support" if direction == "long" else "resistance"

        for _, zone in zones.iterrows():
            if zone["type"] != zone_type:
                continue
            if zone["zone_bottom"] <= bar["close"] <= zone["zone_top"]:
                signals.append({
                    "bar_index": i,
                    "direction": direction,
                    "entry_price": bar["close"],
                    "zone_bottom": zone["zone_bottom"],
                    "zone_top": zone["zone_top"],
                    "bias_1d": bar["bias_1d"],
                    "bias_4h": bar["bias_4h"],
                })
                break

    # Simulate outcome for each signal
    results = []
    for signal in signals:
        result = simulate_outcome(signal, df_15m, rr_target)
        results.append(result)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)
