from data.fetcher import fetch_ohlcv
from indicators.ema import get_ema_signals
from indicators.sr_zones import detect_zones, intact_zones
from strategy.levels import compute_stop, compute_targets, size_trade, is_rejection


def detect_signal(symbol: str, equity: float = 10000.0) -> dict | None:
    df_1d = get_ema_signals(fetch_ohlcv(symbol, "1d", limit=100))
    df_4h = get_ema_signals(fetch_ohlcv(symbol, "4h", limit=100))
    df_15m = fetch_ohlcv(symbol, "15m", limit=200)

    # daily bias drives direction; 4h kept only for the journal record
    df_15m["bias_1d"] = df_1d["trend_bias"].reindex(df_15m.index, method="ffill")
    df_15m["bias_4h"] = df_4h["trend_bias"].reindex(df_15m.index, method="ffill")

    zones = detect_zones(df_15m)

    last_idx = len(df_15m) - 1
    bar = df_15m.iloc[last_idx]
    bias = bar["bias_1d"]

    if bias not in ("bullish", "bearish"):
        return None

    direction = "long" if bias == "bullish" else "short"
    zone_type = "support" if direction == "long" else "resistance"

    # check the latest bar against every box still intact at this bar — a box
    # formed days ago can be retested now, until price closes through it
    zones_now = intact_zones(zones, df_15m.index[last_idx])

    for _, zone in zones_now.iterrows():
        if zone["type"] != zone_type:
            continue
        if is_rejection(direction, bar, zone):
            entry = bar["close"]
            sl = compute_stop(direction, entry, zone, df_15m, last_idx)
            tp1, tp2 = compute_targets(direction, entry, sl, zones_now)
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
