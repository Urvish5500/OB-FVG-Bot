import pandas as pd
import numpy as np

def delta_volume(df: pd.DataFrame) -> pd.Series:
    return np.where(df['close'] > df['open'], df['volume'], -df['volume'])
