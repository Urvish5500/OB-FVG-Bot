"""Manual trade journal — kept in its own `manual_trades` table, separate from
the bot's `trades` table, so the two can be compared (overlaps, bot-only,
manual-only). Trades are logged AFTER exit (completed), using the same
50%-at-2R / 50%-runner model the bot uses.
"""

from datetime import datetime, timedelta
from database.db import get_connection, get_all_trades
from strategy.levels import size_trade

RISK_PCT = 0.004
MATCH_WINDOW_MIN = 30  # bot/manual entries within this many minutes = same setup


def init_manual_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_trades (
            id SERIAL PRIMARY KEY,
            status VARCHAR(10) DEFAULT 'taken',   -- 'taken' or 'skipped'
            symbol VARCHAR(20) NOT NULL,
            direction VARCHAR(10),
            bias_1d VARCHAR(10),
            bias_4h VARCHAR(10),
            entry_price FLOAT,
            entry_time TIMESTAMP,
            stop_loss FLOAT,
            take_profit_1 FLOAT,
            final_exit_price FLOAT,
            exit_reason VARCHAR(20),
            hit_tp1 BOOLEAN,
            risk_reward FLOAT,
            realized_r FLOAT,
            position_size FLOAT,
            notional FLOAT,
            leverage FLOAT,
            equity_at_entry FLOAT,
            pnl_usdt FLOAT,
            pnl_pct FLOAT,
            outcome VARCHAR(20),
            related_bot_trade_id INT,
            screenshot_path TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _parse_time(t):
    return datetime.fromisoformat(t) if isinstance(t, str) else t


def insert_manual_trade(data: dict):
    """Log a completed manual trade. Computes sizing, leverage, blended R and
    PnL from the screenshot fields the user provides."""
    entry = data["entry_price"]
    stop = data["stop_loss"]
    direction = data["direction"]
    equity = data["total_equity"]
    final_exit = data["final_exit_price"]
    hit_tp1 = data["hit_tp1"]

    risk = abs(entry - stop)
    tp1 = entry + 2 * risk if direction == "long" else entry - 2 * risk
    final_R = (final_exit - entry) / risk if direction == "long" else (entry - final_exit) / risk

    # 50% booked at 2R, runner trails with stop at breakeven (floored at 0)
    if hit_tp1:
        realized_R = 1.0 + 0.5 * max(final_R, 0.0)
    else:
        realized_R = max(final_R, -1.0)
    realized_R = round(realized_R, 2)

    pnl_usdt = round(realized_R * RISK_PCT * equity, 2)
    pnl_pct = round(realized_R * RISK_PCT * 100, 2)
    outcome = "win" if realized_R > 0 else "loss" if realized_R < 0 else "breakeven"
    risk_reward = round(abs(final_exit - entry) / risk, 2) if risk > 0 else None
    sizing = size_trade(equity, entry, stop)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO manual_trades (
            status, symbol, direction, bias_1d, bias_4h, entry_price, entry_time,
            stop_loss, take_profit_1, final_exit_price, exit_reason, hit_tp1,
            risk_reward, realized_r, position_size, notional, leverage,
            equity_at_entry, pnl_usdt, pnl_pct, outcome, screenshot_path, notes
        ) VALUES (
            'taken', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id
    """, (
        data["symbol"], direction, data.get("bias_1d"), data.get("bias_4h"),
        entry, _parse_time(data["entry_time"]), stop, tp1, final_exit,
        data.get("exit_reason"), hit_tp1, risk_reward, realized_R,
        sizing["quantity"], sizing["notional"], sizing["leverage"],
        equity, pnl_usdt, pnl_pct, outcome,
        data.get("screenshot_path"), data.get("notes"),
    ))
    tid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ [manual #{tid}] {data['symbol']} {direction} | {outcome} "
          f"| {realized_R}R | R:R {risk_reward} | {sizing['leverage']}x "
          f"| PnL ${pnl_usdt} ({pnl_pct}%)")
    return tid


def log_skipped(symbol: str, entry_time, reason: str, related_bot_trade_id: int = None):
    """Record a bot signal you deliberately passed on, with your reason."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO manual_trades (status, symbol, entry_time, related_bot_trade_id, notes)
        VALUES ('skipped', %s, %s, %s, %s) RETURNING id
    """, (symbol, _parse_time(entry_time), related_bot_trade_id, reason))
    tid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ [skip #{tid}] {symbol} @ {entry_time} — {reason}")
    return tid


def get_manual_trades():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM manual_trades ORDER BY entry_time DESC")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def compare_bot_vs_manual(window_min: int = MATCH_WINDOW_MIN):
    """Match bot trades and manual 'taken' trades on symbol + entry time.
    Returns overlaps, bot-only (you may have missed/skipped), and manual-only."""
    bot = get_all_trades()
    manual = [m for m in get_manual_trades() if m["status"] == "taken"]
    window = timedelta(minutes=window_min)

    overlaps, manual_only = [], []
    matched_bot_ids = set()

    for m in manual:
        match = None
        for b in bot:
            if b["symbol"] != m["symbol"] or b["entry_time"] is None or m["entry_time"] is None:
                continue
            if abs(b["entry_time"] - m["entry_time"]) <= window:
                match = b
                matched_bot_ids.add(b["id"])
                break
        (overlaps if match else manual_only).append(
            {"manual_id": m["id"], "symbol": m["symbol"],
             "bot_id": match["id"] if match else None})

    bot_only = [{"bot_id": b["id"], "symbol": b["symbol"], "entry_time": b["entry_time"]}
                for b in bot if b["id"] not in matched_bot_ids]

    return {
        "overlaps": overlaps,        # both you and the bot took it
        "bot_only": bot_only,        # bot took, you didn't (missed or skipped)
        "manual_only": manual_only,  # you took, bot didn't signal
        "counts": {"overlap": len(overlaps), "bot_only": len(bot_only),
                   "manual_only": len(manual_only)},
    }
