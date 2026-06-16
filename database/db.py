import os
import psycopg2
from dotenv import load_dotenv
from models.trades import Trade

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
            exit_price FLOAT,
            exit_time TIMESTAMP,
            exit_reason VARCHAR(20),
            pnl_pct FLOAT,
            pnl_usdt FLOAT,
            outcome VARCHAR(20),
            screenshot_path TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
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
            stop_loss, take_profit_1, take_profit_2, risk_reward,
            exit_price, exit_time, exit_reason, pnl_pct, pnl_usdt,
            outcome, screenshot_path, notes, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        trade.symbol, trade.direction, trade.indicator_used, trade.entry_timeframe,
        trade.bias_1d, trade.bias_4h, trade.entry_price, trade.entry_time, trade.position_size,
        trade.stop_loss, trade.take_profit_1, trade.take_profit_2, trade.risk_reward,
        trade.exit_price, trade.exit_time, trade.exit_reason, trade.pnl_pct, trade.pnl_usdt,
        trade.outcome, trade.screenshot_path, trade.notes, trade.created_at
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_all_trades():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trades ORDER BY created_at DESC")
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]