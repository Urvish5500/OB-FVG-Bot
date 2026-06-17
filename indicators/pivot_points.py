import pandas as pd


def pivot_high(series: pd.Series, left: int, right: int = 3) -> pd.Series:
    """Pivot high: highest in the `left` bars before and `right` bars after.
    Asymmetric — confirmed ~`right` bars after the pivot forms (not `left`), so
    the live blind spot at the right edge is only `right` bars, not `left`."""
    window = left + right + 1
    rolling_max = series.rolling(window=window, min_periods=window).max()
    # right-aligned max ending at i+right == max over [i-left, i+right]; place at i
    pivot = rolling_max.shift(-right)
    return series.where(series == pivot)


def pivot_low(series: pd.Series, left: int, right: int = 3) -> pd.Series:
    window = left + right + 1
    rolling_min = series.rolling(window=window, min_periods=window).min()
    pivot = rolling_min.shift(-right)
    return series.where(series == pivot)
