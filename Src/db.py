import sqlite3
from typing import Optional, Tuple, Dict, Any

DB_FILE = "bot.db"

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            code TEXT PRIMARY KEY,
            buyer TEXT,
            seller TEXT,
            amount REAL,
            fee REAL,
            ts_added INTEGER,
            admin_add TEXT,
            admin_close TEXT,
            closed INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deal_messages (
            code TEXT PRIMARY KEY,
            chat_id INTEGER,
            message_id INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invite_links (
            link TEXT PRIMARY KEY,
            chat_id INTEGER,
            user_id INTEGER,
            ts INTEGER
        )
    """)
    conn.commit()
    conn.close()

# --- Deals ---
def add_deal(code: str, buyer: str, seller: str, amount: float, fee: float,
             user_id: int, ts: int, admin_add: str) -> str:
    conn = get_conn()
    conn.execute("""
        INSERT INTO deals(code, buyer, seller, amount, fee, ts_added, admin_add)
        VALUES (?,?,?,?,?,?,?)
    """, (code, buyer, seller, amount, fee, ts, admin_add))
    conn.commit()
    conn.close()
    return code

def set_deal_message(code: str, chat_id: int, message_id: int):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO deal_messages(code, chat_id, message_id)
        VALUES (?,?,?)
    """, (code, chat_id, message_id))
    conn.commit()
    conn.close()

def mark_deal_closed(code: str, admin_close: str):
    conn = get_conn()
    conn.execute("""
        UPDATE deals SET closed=1, admin_close=? WHERE code=?
    """, (admin_close, code))
    conn.commit()
    conn.close()

# --- Settings ---
def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None

def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

# --- Invite links ---
def add_invite_link(link: str, chat_id: int, user_id: int, ts: int):
    conn = get_conn()
    conn.execute("""
        INSERT INTO invite_links(link, chat_id, user_id, ts)
        VALUES (?,?,?,?)
    """, (link, chat_id, user_id, ts))
    conn.commit()
    conn.close()
