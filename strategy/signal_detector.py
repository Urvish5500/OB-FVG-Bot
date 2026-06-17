from data.fetcher import fetch_ohlcv
from indicators.ema import get_ema_signals
from indicators.sr_zones import detect_zones
from indicators.volume_analysis import get_volume_signals


def detect_signal(symbol: str) -> dict | None:
    df_1d = get_ema_signals(fetch_ohlcv(symbol, "1d", limit=100))
    df_4h = get_ema_signals(fetch_ohlcv(symbol, "4h", limit=100))
    df_15m = fetch_ohlcv(symbol, "15m", limit=200)

    df_15m = get_volume_signals(df_15m)
    df_15m["bias_1d"] = df_1d["trend_bias"].reindex(df_15m.index, method="ffill")
    df_15m["bias_4h"] = df_4h["trend_bias"].reindex(df_15m.index, method="ffill")

    zones = detect_zones(df_15m)

    bar = df_15m.iloc[-1]
    bias = bar["bias_1d"] if bar["bias_1d"] == bar["bias_4h"] else None

    if bias not in ("bullish", "bearish"):
        return None
    if bar["volume_tier"] not in ("high", "very_high"):
        return None

    direction = "long" if bias == "bullish" else "short"
    zone_type = "support" if direction == "long" else "resistance"

    for _, zone in zones.iterrows():
        if zone["type"] != zone_type:
            continue
        if zone["zone_bottom"] <= bar["close"] <= zone["zone_top"]:
            sl = zone["zone_bottom"] if direction == "long" else zone["zone_top"]
            risk = abs(bar["close"] - sl)
            tp = bar["close"] + 2 * risk if direction == "long" else bar["close"] - 2 * risk
            return {
                "symbol": symbol,
                "direction": direction,
                "entry_price": bar["close"],
                "stop_loss": sl,
                "take_profit_1": tp,
                "bias_1d": bar["bias_1d"],
                "bias_4h": bar["bias_4h"],
            }

    return None
