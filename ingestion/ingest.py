import shutil
from pathlib import Path
from datetime import datetime
from models.trades import Trade
from database.db import insert_trade

SCREENSHOT_DIR = Path("data/trades")


def save_screenshot(src_path: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(src_path).suffix
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dst = SCREENSHOT_DIR / f"{timestamp}{ext}"
    shutil.copy(src_path, dst)
    return str(dst)


def log_trade():
    print("\n--- New Trade Entry ---")

    # Screenshot
    src = input("Screenshot path (drag file here): ").strip().strip("'\"")
    screenshot_path = save_screenshot(src)

    # Identity
    symbol = input("Symbol (e.g. BTCUSDT): ").strip().upper()
    direction = input("Direction (long/short): ").strip().lower()
    indicator_used = input("Indicator (sr_zones/volume_suite): ").strip().lower()

    # Bias
    bias_1d = input("Daily bias (bullish/bearish/neutral): ").strip().lower()
    bias_4h = input("4H bias (bullish/bearish/neutral): ").strip().lower()

    # Entry
    entry_price = float(input("Entry price: "))
    total_equity = float(input("Total equity (USDT): "))
    position_size = round(total_equity * 0.004, 2)
    print(f"  → Position size: ${position_size} USDT (0.4% of ${total_equity})")
    stop_loss = float(input("Stop loss price: "))
    take_profit_1 = float(input("Take profit 1 price: "))
    tp2_input = input("Take profit 2 price (press Enter to skip): ").strip()
    take_profit_2 = float(tp2_input) if tp2_input else None

    # Auto-compute risk/reward
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit_1 - entry_price)
    risk_reward = round(reward / risk, 2) if risk > 0 else None

    # Journal
    notes = input("Notes (press Enter to skip): ").strip() or None

    # Build and save
    trade = Trade(
        symbol=symbol,
        direction=direction,
        indicator_used=indicator_used,
        entry_timeframe="15m",
        bias_1d=bias_1d,
        bias_4h=bias_4h,
        entry_price=entry_price,
        entry_time=datetime.now(),
        position_size=position_size,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        risk_reward=risk_reward,
        screenshot_path=screenshot_path,
        notes=notes,
    )
    insert_trade(trade)
    print(f"\n✓ Trade logged: {symbol} {direction} @ {entry_price} | R:R {risk_reward} | Screenshot saved.")


if __name__ == "__main__":
    log_trade()
