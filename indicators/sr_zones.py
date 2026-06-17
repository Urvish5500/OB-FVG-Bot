import pandas as pd
import numpy as np
from indicators.delta_volume import delta_volume
from indicators.pivot_points import pivot_high, pivot_low

ZONE_COLUMNS = ['bar_index', 'type', 'price', 'zone_top', 'zone_bottom',
                'volume_score', 'status', 'broken_index']


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


def _first_break(close: pd.Series, start_pos: int, level: float, kind: str):
    """First bar position at/after `start_pos` where price CLOSES through the
    box (close above a resistance top, or below a support bottom). Returns the
    integer position, or None if the box never breaks within the data."""
    seg = close.iloc[start_pos:]
    mask = (seg > level) if kind == 'resistance' else (seg < level)
    if mask.any():
        return start_pos + int(mask.values.argmax())   # argmax → first True
    return None


def detect_zones(df: pd.DataFrame, lookback: int = 30, vol_len: int = 2, box_width: float = 1.0, right: int = 3) -> pd.DataFrame:
    dv = delta_volume(df)

    vol_scaled = dv / 2.5
    vol_hi = vol_scaled.rolling(window=vol_len).max()
    vol_lo = vol_scaled.rolling(window=vol_len).min()

    zone_width = atr(df) * box_width

    ph = pivot_high(df['high'], lookback, right)
    pl = pivot_low(df['low'], lookback, right)

    close = df['close']
    zones = []
    last = len(df) - 1

    for i in range(len(df)):
        # the pivot is at bar i but only confirmed `right` bars later — the box
        # is not tradeable until then, so anchor availability to the confirm bar
        confirm_pos = min(i + right, last)
        idx = df.index[confirm_pos]

        if not pd.isna(ph.iloc[i]) and dv.iloc[i] < vol_lo.iloc[i]:
            top = ph.iloc[i] + zone_width.iloc[i]
            bottom = ph.iloc[i]
            # box stays intact (retestable) until a close prints above its top
            broken_pos = _first_break(close, confirm_pos, top, 'resistance')
            zones.append({
                'bar_index': idx,
                'type': 'resistance',
                'price': ph.iloc[i],
                'zone_top': top,
                'zone_bottom': bottom,
                'volume_score': round(dv.iloc[i], 2),
                'status': 'broken' if broken_pos is not None else 'intact',
                'broken_index': df.index[broken_pos] if broken_pos is not None else pd.NaT,
            })

        if not pd.isna(pl.iloc[i]) and dv.iloc[i] > vol_hi.iloc[i]:
            top = pl.iloc[i]
            bottom = pl.iloc[i] - zone_width.iloc[i]
            # box stays intact until a close prints below its bottom
            broken_pos = _first_break(close, confirm_pos, bottom, 'support')
            zones.append({
                'bar_index': idx,
                'type': 'support',
                'price': pl.iloc[i],
                'zone_top': top,
                'zone_bottom': bottom,
                'volume_score': round(dv.iloc[i], 2),
                'status': 'broken' if broken_pos is not None else 'intact',
                'broken_index': df.index[broken_pos] if broken_pos is not None else pd.NaT,
            })

    if not zones:
        return pd.DataFrame(columns=ZONE_COLUMNS)

    out = pd.DataFrame(zones)
    out['broken_index'] = pd.to_datetime(out['broken_index'])
    return out


def intact_zones(zones: pd.DataFrame, ts) -> pd.DataFrame:
    """Boxes that are live at bar timestamp `ts`: already confirmed (no
    lookahead) and not yet closed through. A box breaks on the bar it closes
    through, so it is usable while broken_index is still in the future."""
    if zones.empty:
        return zones
    formed = zones['bar_index'] <= ts
    still_live = zones['broken_index'].isna() | (zones['broken_index'] > ts)
    return zones[formed & still_live]
