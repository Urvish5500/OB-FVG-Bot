import os
import psycopg2
from dotenv import load_dotenv
from models.trades import Trade
from strategy.levels import fee_in_R, RISK_PCT

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
            realized_r FLOAT,
            tp1_filled BOOLEAN DEFAULT FALSE,
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
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS realized_r FLOAT")
    cur.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS tp1_filled BOOLEAN DEFAULT FALSE")
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


def mark_tp1_filled(trade_id: int):
    """Book the 50% at TP1: flag the trade. The working stop is then breakeven
    (entry) — derived from this flag, so no separate stop column is needed."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE trades SET tp1_filled = TRUE WHERE id = %s", (trade_id,))
    conn.commit()
    cur.close()
    conn.close()


def close_trade(trade_id: int, runner_exit_price: float, hit_tp1: bool,
                exit_reason: str, final_is_market: bool, notes: str = None):
    """Finalize an open trade with the blended 50%@TP1 / 50%@runner model — the
    exact math as backtest.simulate_outcome and the manual journal. The half
    booked at TP1 is worth +1.0R; the runner adds 0.5 * its R from entry (floored
    at breakeven once TP1 filled). Records gross R, fees (shared model), and net.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT entry_price, direction, position_size, stop_loss, take_profit_1 "
        "FROM trades WHERE id = %s", (trade_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"No trade with id {trade_id}")

    entry, direction, qty, sl, tp1 = row
    sign = 1 if direction == "long" else -1
    risk = abs(entry - sl)
    one_R = qty * risk                                   # $ value of 1R (= RISK_PCT * equity)

    runner_R = sign * (runner_exit_price - entry) / risk if risk else 0.0
    if hit_tp1:
        realized_R = round(1.0 + 0.5 * max(runner_R, 0.0), 2)
    else:
        realized_R = round(max(runner_R, -1.0), 2)

    fee_R = fee_in_R(entry, sl, tp1, runner_exit_price, hit_tp1, final_is_market)
    fees_usdt = round(fee_R * one_R, 2)
    fees_r = round(fee_R, 2)
    pnl_usdt = round(realized_R * one_R, 2)
    pnl_pct = round(realized_R * RISK_PCT * 100, 2)       # % of equity, like the journal
    net_pnl_usdt = round(pnl_usdt - fees_usdt, 2)
    net_r = round(realized_R - fee_R, 2)
    # outcome on gross R, to match the journal and backtest (a TP1-then-BE is +1R = win)
    outcome = "win" if realized_R > 0 else "loss" if realized_R < 0 else "breakeven"

    cur.execute("""
        UPDATE trades
        SET exit_price = %s, exit_time = NOW(), exit_reason = %s, tp1_filled = %s,
            realized_r = %s, pnl_usdt = %s, pnl_pct = %s,
            fees_usdt = %s, fees_r = %s, net_pnl_usdt = %s, net_r = %s, outcome = %s,
            notes = COALESCE(notes || ' | ' || %s, notes, %s)
        WHERE id = %s
    """, (runner_exit_price, exit_reason, hit_tp1, realized_R, pnl_usdt, pnl_pct,
          fees_usdt, fees_r, net_pnl_usdt, net_r, outcome, notes, notes, trade_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Trade {trade_id} closed [{exit_reason}] @ {runner_exit_price} | {outcome} "
          f"| {realized_R}R gross | fees ${fees_usdt} ({fees_r}R) | NET {net_r}R / ${net_pnl_usdt}")
    return {"trade_id": trade_id, "outcome": outcome, "realized_r": realized_R,
            "net_r": net_r, "net_pnl_usdt": net_pnl_usdt}
    return {"trade_id": trade_id, "outcome": outcome, "pnl_usdt": pnl_usdt,
            "pnl_pct": pnl_pct, "fees_usdt": fees_usdt, "net_pnl_usdt": net_pnl_usdt,
            "net_r": net_r}