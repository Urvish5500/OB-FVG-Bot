import sys
import json
from datetime import datetime
from models.trades import Trade
from database.db import insert_trade


def log_from_parsed(data: dict):
    risk = abs(data["entry_price"] - data["stop_loss"])
    reward = abs(data["take_profit_1"] - data["entry_price"])
    risk_reward = round(reward / risk, 2) if risk > 0 else None
    position_size = round(data["total_equity"] * 0.004, 2)

    trade = Trade(
        symbol=data["symbol"],
        direction=data["direction"],
        indicator_used=data.get("indicator_used", "sr_zones"),
        entry_timeframe="15m",
        bias_1d=data["bias_1d"],
        bias_4h=data["bias_4h"],
        entry_price=data["entry_price"],
        entry_time=datetime.now(),
        position_size=position_size,
        stop_loss=data["stop_loss"],
        take_profit_1=data["take_profit_1"],
        take_profit_2=data.get("take_profit_2"),
        risk_reward=risk_reward,
        screenshot_path=data.get("screenshot_path"),
        notes=data.get("notes"),
    )
    insert_trade(trade)
    print(f"✓ {trade.symbol} {trade.direction} @ {trade.entry_price} | R:R {risk_reward} | Size ${position_size}")


if __name__ == "__main__":
    data = json.loads(sys.argv[1])
    log_from_parsed(data)
