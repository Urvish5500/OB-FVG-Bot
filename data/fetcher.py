import time
import ccxt
import pandas as pd

PAGE = 1000  # Binance's max bars per OHLCV call


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """Fetch the most recent `limit` OHLCV bars, paging backward through
    Binance's 1000-bar-per-call cap so a full year of 15m data is reachable."""
    exchange = ccxt.binance()
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - limit * tf_ms

    rows = []
    while len(rows) < limit:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=PAGE)
        if not batch:
            break
        rows += batch
        since = batch[-1][0] + tf_ms          # next page starts after last bar
        if len(batch) < PAGE:                 # reached the present
            break
        time.sleep(exchange.rateLimit / 1000)  # respect the rate limit

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.tail(limit)                       # keep the most recent `limit` bars
