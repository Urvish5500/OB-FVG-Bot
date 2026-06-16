import pandas as pd
import numpy as np


def pivot_high(series: pd.Series, lookback: int) -> pd.Series:
    n = lookback
    rolling_max = series.rolling(window=2*n+1, center=True, min_periods=2*n+1).max()
    return series.where(series == rolling_max)


def pivot_low(series: pd.Series, lookback: int) -> pd.Series:
    n = lookback
    rolling_min = series.rolling(window=2*n+1, center=True, min_periods=2*n+1).min()
    return series.where(series == rolling_min)