# OB-FVG-Bot

An algorithmic trading bot built on an Order Block (OB) + Fair Value Gap (FVG) strategy, targeting crypto perpetual futures on Binance.

## Strategy Overview

- **Bias:** Daily (1D) and 4-Hour (4H) timeframes for directional bias
- **Entry:** 15-minute timeframe for precise entry timing
- **Core Concepts:** Order Blocks, Fair Value Gaps, market structure

## Project Structure

```
OB-FVG-Bot/
├── data/
│   ├── raw/          # OHLCV price data from exchange
│   ├── processed/    # Cleaned data ready for analysis
│   └── trades/       # Trade screenshots + journal entries
├── indicators/       # Python equivalents of Pine Script indicators
├── strategy/         # Rules engine (entry/exit logic)
├── backtest/         # Backtesting engine
├── database/         # SQLite schema + trade database
├── ingestion/        # Screenshot + journal parsing pipeline
├── notebooks/        # Exploratory analysis
└── tests/            # Unit tests
```

## Setup

```bash
# Clone the repo
git clone https://github.com/Urvish5500/OB-FVG-Bot.git
cd OB-FVG-Bot

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Then edit .env with your actual API keys
```

## Build Progress

- [ ] Step 0: Dev environment + project structure
- [ ] Step 1: Pine Script → Python indicator translation
- [ ] Step 2: Trade schema design
- [ ] Step 3: Database build
- [ ] Step 4: Screenshot + journal ingestion pipeline
- [ ] Step 5: Backtesting engine
- [ ] Step 6: Binance live integration

## Tech Stack

- **Language:** Python 3.13
- **Exchange:** Binance (via `ccxt`)
- **Indicators:** `pandas-ta`
- **Backtesting:** `vectorbt`
- **Database:** SQLite
- **AI Parsing:** Claude API (Anthropic)
