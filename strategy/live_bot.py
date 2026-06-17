import time
from datetime import datetime
from strategy.signal_detector import detect_signal
from models.trades import Trade
from database.db import insert_trade

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TOTAL_EQUITY = 10000.0


def log_signal(signal: dict):
    position_size = round(TOTAL_EQUITY * 0.004, 2)
    risk = abs(signal["entry_price"] - signal["stop_loss"])
    reward = abs(signal["take_profit_1"] - signal["entry_price"])
    risk_reward = round(reward / risk, 2) if risk > 0 else None

    trade = Trade(
        symbol=signal["symbol"].replace("/", ""),
        direction=signal["direction"],
        indicator_used="sr_zones",
        entry_timeframe="15m",
        bias_1d=signal["bias_1d"],
        bias_4h=signal["bias_4h"],
        entry_price=signal["entry_price"],
        entry_time=datetime.now(),
        position_size=position_size,
        stop_loss=signal["stop_loss"],
        take_profit_1=signal["take_profit_1"],
        risk_reward=risk_reward,
    )
    insert_trade(trade)
    print(f"  ✓ Signal logged: {trade.symbol} {trade.direction} @ {trade.entry_price} | R:R {risk_reward}")


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
                signal = detect_signal(symbol)
                if signal:
                    log_signal(signal)
                else:
                    print(f"  No signal: {symbol}")
        time.sleep(60)


if __name__ == "__main__":
    run()
