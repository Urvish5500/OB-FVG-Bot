from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    # Identity
    symbol: str
    direction: str  # "long" or "short"
    indicator_used: str  # "sr_zones" or "volume_suite"

    # Timeframes
    entry_timeframe: str  # "15m"
    bias_1d: str  # "bullish", "bearish", "neutral"
    bias_4h: str  # "bullish", "bearish", "neutral"

    # Entry
    entry_price: float
    entry_time: datetime
    position_size: float

    # Risk
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    risk_reward: Optional[float] = None

    # Sizing
    notional: Optional[float] = None   # position value in USDT (quantity * entry)
    leverage: Optional[float] = None   # leverage needed to hold notional (min 1x)

    # Exit
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None  # "tp1", "tp2", "sl", "manual"

    # Outcome
    pnl_pct: Optional[float] = None
    pnl_usdt: Optional[float] = None
    outcome: Optional[str] = None  # "win", "loss", "breakeven"

    # Journal
    screenshot_path: Optional[str] = None
    notes: Optional[str] = None

    # Auto-filled
    created_at: datetime = field(default_factory=datetime.now)