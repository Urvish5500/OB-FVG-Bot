# OB-FVG-Bot

An algorithmic trading bot for crypto on Binance. It detects high-volume
support/resistance zones, takes rejection entries in the direction of the daily
trend, and logs every signal to a database for review. It runs 24/7 on a VPS in
paper-trading mode, alongside a manual journal used to compare the bot's signals
against discretionary trades.

> The name is historical. The implemented strategy is **S&R box rejection**
> (ChartPrime "SR Breaks and Retests") plus an EMA daily-bias filter — not the
> Order Block / FVG approach the name suggests.

## Strategy

- **Bias:** daily EMA(12/21/50) trend sets direction (bullish → long, bearish → short).
  4H bias is recorded for the journal but does not gate entries.
- **Entry (15m):** price must *reject* a matching S&R box — wick into the box and
  close back out in the bias direction. Support box for longs, resistance for shorts.
- **S&R zones:** ChartPrime "SR Breaks and Retests" ported to Python — lookback 30,
  delta-volume filter length 2, box width 1 (matches the TradingView indicator).
- **Stop loss:** the farther of the box edge or the recent 20-bar swing.
- **Targets:** TP1 at 2R books 50%; the runner trails to the nearest opposing box
  (or 3R if none) and books the other 50%. Stop moves to breakeven after TP1.
- **Sizing:** risk-based — a stop-out always loses exactly 0.4% of equity. Leverage
  is whatever is needed to hold the position (min 1x), like a manual trade calculator.

> **Honest note:** the bare mechanical rule is unprofitable in backtest
> (profit factor ~0.3 on BTC + ETH over a year). The intended edge is
> discretionary selectivity — *which* rejections to take — recovered by comparing
> the bot's signals against the manual journal.

## Project structure

```
OB-FVG-Bot/
├── data/
│   ├── fetcher.py     # Binance OHLCV via ccxt
│   └── trades/        # saved trade screenshots
├── indicators/        # delta_volume, pivot_points, ema, sr_zones, volume_analysis
├── strategy/
│   ├── levels.py          # stop / target / rejection / risk-based sizing
│   ├── signal_detector.py # latest-bar signal check
│   └── live_bot.py        # 24/7 loop, scans every 15m close
├── backtest/          # engine.py (multi-symbol) + metrics.py (realized R)
├── database/
│   ├── db.py              # Supabase: trades table, insert/close
│   └── manual_journal.py  # separate manual_trades table + bot-vs-manual compare
├── ingestion/         # ai_log.py (parse screenshot) + ingest.py (CLI)
├── models/trades.py   # Trade dataclass
├── deploy/            # systemd service + VPS setup notes
└── tests/
```

## Setup (local)

```bash
git clone https://github.com/Urvish5500/OB-FVG-Bot.git
cd OB-FVG-Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add DATABASE_URL (Supabase connection string)
python -c "from database.db import init_db; init_db()"   # create tables
```

## Running

```bash
python -m strategy.live_bot          # live signal loop (BTC + ETH, every 15m)
python -m ingestion.ingest           # manual trade logging (CLI fallback)
python -c "from backtest.engine import run_multi_backtest; \
           from backtest.metrics import calculate_metrics; \
           print(calculate_metrics(run_multi_backtest()))"   # backtest
```

## Deployment

Runs 24/7 on a Hetzner VPS as a `systemd` service (`ob-fvg-bot.service`) with
auto-restart and logging to `bot.log`. See [`deploy/README.md`](deploy/README.md)
for setup and monitoring commands. Uses `requirements-live.txt` (minimal) on the
server; the full `requirements.txt` is for local dev.

## Build status

- [x] Step 0: Dev environment + project structure
- [x] Step 1: Pine Script → Python indicators
- [x] Step 2: Trade schema (`models/trades.py`)
- [x] Step 3: Database (Supabase / PostgreSQL)
- [x] Step 4: Screenshot + journal ingestion (AI parsing + manual journal)
- [x] Step 5: Backtesting engine (BTC + ETH)
- [x] Step 6: Binance live integration (paper) + VPS deployment

Next: accumulate paper trades on both sides, then mine the bot-vs-manual
comparison to add the entry filter that captures the discretionary edge.

## Tech stack

- **Language:** Python 3.13
- **Exchange / data:** Binance via `ccxt`
- **Analysis:** `pandas`, `numpy` (custom indicators, no pandas-ta/vectorbt)
- **Database:** Supabase (PostgreSQL via `psycopg2`)
- **Config:** `python-dotenv`
- **Hosting:** Hetzner VPS (Ubuntu, systemd)
