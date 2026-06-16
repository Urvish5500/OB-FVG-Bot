import pandas as pd
import numpy as np


def calculate_rvol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    avg_volume = df["volume"].rolling(period).mean()
    return df["volume"] / avg_volume


def get_volume_signals(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    result = df.copy()
    result["rvol"] = calculate_rvol(df, period)
    conditions = [result["rvol"].isna(), result["rvol"] < 0.5, result["rvol"] < 1.0, result["rvol"] < 2.0]
    choices = ["unknown", "low", "normal", "high"]
    result["volume_tier"] = np.select(conditions, choices, default="very_high")
    return result