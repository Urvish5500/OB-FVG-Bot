import pandas as pd
import numpy as np
from indicators.delta_volume import delta_volume
from indicators.pivot_points import pivot_high, pivot_low

def atr(df: pd.DataFrame, period: int = 200) -> pd.Series:
    high = df['high']
    low = df['low']
    prev_close = df['close'].shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    return tr.rolling(window=period, min_periods=1).mean()


def detect_zones(df: pd.DataFrame, lookback: int = 30, vol_len: int = 2, box_width: float = 1.0, right: int = 3) -> pd.DataFrame:
    dv = delta_volume(df)

    vol_scaled = dv / 2.5
    vol_hi = vol_scaled.rolling(window=vol_len).max()
    vol_lo = vol_scaled.rolling(window=vol_len).min()

    zone_width = atr(df) * box_width

    ph = pivot_high(df['high'], lookback, right)
    pl = pivot_low(df['low'], lookback, right)

    zones = []
    last = len(df) - 1

    for i in range(len(df)):
        # the pivot is at bar i but only confirmed `right` bars later — the box
        # is not tradeable until then, so anchor availability to the confirm bar
        idx = df.index[min(i + right, last)]

        if not pd.isna(ph.iloc[i]) and dv.iloc[i] < vol_lo.iloc[i]:
            zones.append({
                'bar_index': idx,
                'type': 'resistance',
                'price': ph.iloc[i],
                'zone_top': ph.iloc[i] + zone_width.iloc[i],
                'zone_bottom': ph.iloc[i],
                'volume_score': round(dv.iloc[i], 2),
                'status': 'intact'
            })

        if not pd.isna(pl.iloc[i]) and dv.iloc[i] > vol_hi.iloc[i]:
            zones.append({
                'bar_index': idx,
                'type': 'support',
                'price': pl.iloc[i],
                'zone_top': pl.iloc[i],
                'zone_bottom': pl.iloc[i] - zone_width.iloc[i],
                'volume_score': round(dv.iloc[i], 2),
                'status': 'intact'
            })

    if not zones:
        return pd.DataFrame(columns=['bar_index', 'type', 'price', 'zone_top', 'zone_bottom', 'volume_score', 'status'])

    return pd.DataFrame(zones)

