# db.py
import sqlite3
from typing import Optional, List, Dict
from .utils import now_ts

DB_PATH = "bot.db"

# ----------------- DB Connection -----------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
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
    CREATE TABLE IF NOT EXISTS groups(
        chat_id INTEGER PRIMARY KEY,
        title TEXT
    )
    """)

    # Deals
    c.execute("""
    CREATE TABLE IF NOT EXISTS deals(
        code TEXT PRIMARY KEY,
        buyer TEXT,
        seller TEXT,
        amount REAL,
        fee REAL,
        ts INTEGER,
        admin_add TEXT,
        admin_close TEXT,
        message_chat_id INTEGER,
        message_id INTEGER,
        closed INTEGER DEFAULT 0
    )
    """)

    # Settings
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()

# ----------------- Settings -----------------
def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key: str, value: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
    conn.commit()
    conn.close()

# ----------------- Deals -----------------
def add_deal(code: str, buyer: str, seller: str, amount: float, fee: float, ts: int, admin_add: str, admin_close: Optional[str] = None) -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals(code, buyer, seller, amount, fee, ts, admin_add, admin_close, closed)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (code, buyer, seller, amount, fee, ts, admin_add, admin_close, 0))
    conn.commit()
    conn.close()
    return code

def set_deal_message(code: str, chat_id: int, message_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE deals SET message_chat_id=?, message_id=? WHERE code=?", (chat_id, message_id, code))
    conn.commit()
    conn.close()

def mark_deal_closed(code: str, admin_close: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE deals SET closed=1, admin_close=? WHERE code=?", (admin_close, code))
    conn.commit()
    conn.close()

def get_deal(code: str) -> Optional[Dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()
    if row:
        keys = ["code","buyer","seller","amount","fee","ts","admin_add","admin_close","message_chat_id","message_id","closed"]
        return dict(zip(keys, row))
    return None
