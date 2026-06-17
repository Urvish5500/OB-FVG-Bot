from data.fetcher import fetch_ohlcv
from indicators.ema import get_ema_signals
from indicators.sr_zones import detect_zones
from indicators.volume_analysis import get_volume_signals
from strategy.levels import compute_stop, compute_targets, size_trade


def detect_signal(symbol: str, equity: float = 10000.0) -> dict | None:
    df_1d = get_ema_signals(fetch_ohlcv(symbol, "1d", limit=100))
    df_4h = get_ema_signals(fetch_ohlcv(symbol, "4h", limit=100))
    df_15m = fetch_ohlcv(symbol, "15m", limit=200)

    df_15m = get_volume_signals(df_15m)
    df_15m["bias_1d"] = df_1d["trend_bias"].reindex(df_15m.index, method="ffill")
    df_15m["bias_4h"] = df_4h["trend_bias"].reindex(df_15m.index, method="ffill")

    zones = detect_zones(df_15m)

    last_idx = len(df_15m) - 1
    bar = df_15m.iloc[last_idx]
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
            entry = bar["close"]
            sl = compute_stop(direction, entry, zone, df_15m, last_idx)
            tp1, tp2 = compute_targets(direction, entry, sl, zones)
            sizing = size_trade(equity, entry, sl)
            return {
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry,
                "stop_loss": sl,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "position_size": sizing["quantity"],
                "notional": sizing["notional"],
                "leverage": sizing["leverage"],
                "bias_1d": bar["bias_1d"],
                "bias_4h": bar["bias_4h"],
            }

    return None
