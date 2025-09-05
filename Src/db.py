import sqlite3
from typing import Optional, Dict, Any

DB_FILE = "bot.db"

# ----------------- Database Connection -----------------
def get_conn():
    return sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Users
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        skeleton TEXT,
        ts INTEGER
    )
    """)

    # Groups
    c.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT
    )
    """)

    # Deals
    c.execute("""
    CREATE TABLE IF NOT EXISTS deals (
        code TEXT PRIMARY KEY,
        buyer TEXT,
        seller TEXT,
        amount REAL,
        fee REAL,
        ts INTEGER,
        admin_add TEXT,
        admin_close TEXT,
        chat_id INTEGER,
        message_id INTEGER
    )
    """)

    # Invite links
    c.execute("""
    CREATE TABLE IF NOT EXISTS invite_links (
        link TEXT PRIMARY KEY,
        chat_id INTEGER,
        user_id INTEGER,
        ts INTEGER
    )
    """)

    # Settings
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()

# ----------------- Deal Operations -----------------
def add_deal(code: str, buyer: str, seller: str, amount: float, fee: float,
             admin_user_id: int, ts: int, admin_add: str = "") -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals(code, buyer, seller, amount, fee, ts, admin_add)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (code, buyer, seller, amount, fee, ts, admin_add))
    conn.commit()
    conn.close()
    return code

def set_deal_message(code: str, chat_id: int, message_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE deals SET chat_id=?, message_id=? WHERE code=?", (chat_id, message_id, code))
    conn.commit()
    conn.close()

def mark_deal_closed(code: str, admin_close: str = ""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE deals SET admin_close=? WHERE code=?", (admin_close, code))
    conn.commit()
    conn.close()

# ----------------- Settings -----------------
def set_setting(key: str, value: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("REPLACE INTO settings(key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ----------------- Invite Links -----------------
def add_invite_link(link: str, chat_id: int, user_id: int, ts: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO invite_links(link, chat_id, user_id, ts) VALUES (?,?,?,?)", (link, chat_id, user_id, ts))
    conn.commit()
    conn.close()
