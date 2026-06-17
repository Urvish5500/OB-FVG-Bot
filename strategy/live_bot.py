import time
from datetime import datetime
from strategy.signal_detector import detect_signal
from models.trades import Trade
from database.db import insert_trade

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TOTAL_EQUITY = 10000.0


def log_signal(signal: dict):
    entry = signal["entry_price"]
    risk = abs(entry - signal["stop_loss"])
    # R:R reported against the runner target (TP2), matching the hand-drawn setups
    reward = abs(signal["take_profit_2"] - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else None

    trade = Trade(
        symbol=signal["symbol"].replace("/", ""),
        direction=signal["direction"],
        indicator_used="sr_zones",
        entry_timeframe="15m",
        bias_1d=signal["bias_1d"],
        bias_4h=signal["bias_4h"],
        entry_price=entry,
        entry_time=datetime.now(),
        position_size=signal["position_size"],
        stop_loss=signal["stop_loss"],
        take_profit_1=signal["take_profit_1"],
        take_profit_2=signal["take_profit_2"],
        risk_reward=risk_reward,
        notional=signal["notional"],
        leverage=signal["leverage"],
    )
    insert_trade(trade)
    print(f"  ✓ {trade.symbol} {trade.direction} @ {entry} | SL {trade.stop_loss} "
          f"| TP1 {trade.take_profit_1} | TP2 {trade.take_profit_2} "
          f"| R:R {risk_reward} | qty {trade.position_size} "
          f"| {trade.leverage}x (${trade.notional})")


def run():
    print(f"OB-FVG-Bot live — watching {', '.join(SYMBOLS)}")
    print("Signals logged to Supabase on every 15m candle close.")
    print("Press Ctrl+C to stop.\n")

    last_checked_minute = -1

    while True:
        now = datetime.now()
        if now.minute % 15 == 0 and now.minute != last_checked_minute:
            last_checked_minute = now.minute
            print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Scanning {', '.join(SYMBOLS)}...")
            for symbol in SYMBOLS:
                signal = detect_signal(symbol, equity=TOTAL_EQUITY)
                if signal:
                    log_signal(signal)
                else:
                    print(f"  No signal: {symbol}")
        time.sleep(60)


if __name__ == "__main__":
    run()
