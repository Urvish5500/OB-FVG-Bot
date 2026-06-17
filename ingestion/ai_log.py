import sys
import json
from datetime import datetime
from models.trades import Trade
from database.db import insert_trade
from strategy.levels import size_trade


def log_from_parsed(data: dict):
    entry = data["entry_price"]
    risk = abs(entry - data["stop_loss"])
    # R:R reported against the runner target (TP2) if drawn, else TP1
    target = data.get("take_profit_2") or data["take_profit_1"]
    reward = abs(target - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else None
    # risk-based size + leverage: a stop-out loses exactly 0.4% of equity
    sizing = size_trade(data["total_equity"], entry, data["stop_loss"])

    trade = Trade(
        symbol=data["symbol"],
        direction=data["direction"],
        indicator_used=data.get("indicator_used", "sr_zones"),
        entry_timeframe="15m",
        bias_1d=data["bias_1d"],
        bias_4h=data["bias_4h"],
        entry_price=entry,
        entry_time=datetime.now(),
        position_size=sizing["quantity"],
        stop_loss=data["stop_loss"],
        take_profit_1=data["take_profit_1"],
        take_profit_2=data.get("take_profit_2"),
        risk_reward=risk_reward,
        notional=sizing["notional"],
        leverage=sizing["leverage"],
        screenshot_path=data.get("screenshot_path"),
        notes=data.get("notes"),
    )
    trade_id = insert_trade(trade)
    print(f"✓ [#{trade_id}] {trade.symbol} {trade.direction} @ {entry} "
          f"| R:R {risk_reward} | qty {sizing['quantity']} "
          f"| {sizing['leverage']}x (${sizing['notional']})")


if __name__ == "__main__":
    data = json.loads(sys.argv[1])
    log_from_parsed(data)
