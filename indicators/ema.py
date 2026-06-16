import pandas as pd
import numpy as np


def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
    return df["close"].ewm(span=period, adjust=False).mean()


def get_ema_signals(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["ema_12"] = calculate_ema(df, 12)
    result["ema_21"] = calculate_ema(df, 21)
    result["ema_50"] = calculate_ema(df, 50)
    bull_cross = (result["ema_12"] > result["ema_21"]) & (result["ema_12"].shift(1) <= result["ema_21"].shift(1))
    bear_cross = (result["ema_12"] < result["ema_21"]) & (result["ema_12"].shift(1) >= result["ema_21"].shift(1))
    result["crossover"] = np.select([bull_cross, bear_cross], ["bull_cross", "bear_cross"], default="")
    bullish = (result["ema_12"] > result["ema_21"]) & (result["ema_21"] > result["ema_50"])
    bearish = (result["ema_12"] < result["ema_21"]) & (result["ema_21"] < result["ema_50"])
    result["trend_bias"] = np.select([bullish, bearish], ["bullish", "bearish"], default="neutral")

    return result