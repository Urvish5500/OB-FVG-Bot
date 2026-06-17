import os
import psycopg2
from dotenv import load_dotenv
from models.trades import Trade
from strategy.levels import MAKER_FEE, TAKER_FEE, exit_is_maker

load_dotenv()


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            direction VARCHAR(10) NOT NULL,
            indicator_used VARCHAR(50) NOT NULL,
            entry_timeframe VARCHAR(10) NOT NULL,
            bias_1d VARCHAR(10) NOT NULL,
            bias_4h VARCHAR(10) NOT NULL,
            entry_price FLOAT NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            position_size FLOAT NOT NULL,
            stop_loss FLOAT NOT NULL,
            take_profit_1 FLOAT NOT NULL,
            take_profit_2 FLOAT,
            risk_reward FLOAT,
            notional FLOAT,
            leverage FLOAT,
            exit_price FLOAT,
            exit_time TIMESTAMP,
            exit_reason VARCHAR(20),
            pnl_pct FLOAT,
            pnl_usdt FLOAT,
            fees_usdt FLOAT,
            fees_r FLOAT,
            net_pnl_usdt FLOAT,
            net_r FLOAT,
            outcome VARCHAR(20),
            screenshot_path TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    # migrations for tables created before these columns existed
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS notional FLOAT")
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS leverage FLOAT")
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS fees_usdt FLOAT")
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS fees_r FLOAT")
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS net_pnl_usdt FLOAT")
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS net_r FLOAT")
    conn.commit()
    cur.close()
    conn.close()


def insert_trade(trade: Trade):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO trades (
            symbol, direction, indicator_used, entry_timeframe,
            bias_1d, bias_4h, entry_price, entry_time, position_size,
            stop_loss, take_profit_1, take_profit_2, risk_reward, notional, leverage,
            exit_price, exit_time, exit_reason, pnl_pct, pnl_usdt,
            outcome, screenshot_path, notes, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id
    """, (
        trade.symbol, trade.direction, trade.indicator_used, trade.entry_timeframe,
        trade.bias_1d, trade.bias_4h, trade.entry_price, trade.entry_time, trade.position_size,
        trade.stop_loss, trade.take_profit_1, trade.take_profit_2, trade.risk_reward,
        trade.notional, trade.leverage,
        trade.exit_price, trade.exit_time, trade.exit_reason, trade.pnl_pct, trade.pnl_usdt,
        trade.outcome, trade.screenshot_path, trade.notes, trade.created_at
    ))
    trade_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return trade_id


def get_all_trades():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trades ORDER BY created_at DESC")
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def get_open_trades():
    """Trades that have been entered but not yet closed (no outcome recorded)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trades WHERE outcome IS NULL ORDER BY entry_time DESC")
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def close_trade(trade_id: int, exit_price: float, exit_reason: str = "manual",
                notes: str = None):
    """Record the exit of an open trade and compute its P&L and outcome."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT entry_price, direction, position_size, stop_loss FROM trades WHERE id = %s",
        (trade_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"No trade with id {trade_id}")

    entry_price, direction, qty, stop_loss = row
    sign = 1 if direction == "long" else -1
    pnl_usdt = round(sign * (exit_price - entry_price) * qty, 2)
    pnl_pct = round(sign * (exit_price - entry_price) / entry_price * 100, 2)

    # Fees via the shared model: entry filled as a limit (maker); the exit is
    # maker only for take-profit reasons, else taker (stop/manual/market close).
    exit_rate = MAKER_FEE if exit_is_maker(exit_reason) else TAKER_FEE
    fees_usdt = round(qty * entry_price * MAKER_FEE + qty * exit_price * exit_rate, 2)
    net_pnl_usdt = round(pnl_usdt - fees_usdt, 2)
    risk = abs(entry_price - stop_loss)
    one_R = qty * risk                                   # = RISK_PCT * equity_at_entry
    fees_r = round(fees_usdt / one_R, 2) if one_R > 0 else None
    net_r = round(net_pnl_usdt / one_R, 2) if one_R > 0 else None
    # outcome classified on gross PnL, to match the journal and backtest
    outcome = "win" if pnl_usdt > 0 else "loss" if pnl_usdt < 0 else "breakeven"

    cur.execute("""
        UPDATE trades
        SET exit_price = %s, exit_time = NOW(), exit_reason = %s,
            pnl_usdt = %s, pnl_pct = %s,
            fees_usdt = %s, fees_r = %s, net_pnl_usdt = %s, net_r = %s, outcome = %s,
            notes = COALESCE(notes || ' | ' || %s, notes, %s)
        WHERE id = %s
    """, (exit_price, exit_reason, pnl_usdt, pnl_pct,
          fees_usdt, fees_r, net_pnl_usdt, net_r, outcome, notes, notes, trade_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Trade {trade_id} closed @ {exit_price} | {outcome} "
          f"| gross ${pnl_usdt} | fees ${fees_usdt} ({fees_r}R) | NET ${net_pnl_usdt} ({net_r}R)")
    return {"trade_id": trade_id, "outcome": outcome, "pnl_usdt": pnl_usdt,
            "pnl_pct": pnl_pct, "fees_usdt": fees_usdt, "net_pnl_usdt": net_pnl_usdt,
            "net_r": net_r}