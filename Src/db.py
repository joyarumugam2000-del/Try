import sqlite3
from typing import Optional, List
from .config import DB_PATH

# ----------------- Database Connection -----------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        skeleton TEXT,
        last_seen INTEGER,
        trusted INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        is_dva INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS seen_usernames (
        chat_id INTEGER,
        username TEXT,
        skeleton TEXT,
        last_seen INTEGER,
        PRIMARY KEY (chat_id, username)
    );

    CREATE TABLE IF NOT EXISTS suspects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        username TEXT,
        matched_username TEXT,
        score INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        created_at INTEGER,
        decided_by INTEGER
    );

    CREATE TABLE IF NOT EXISTS gban (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        by_id INTEGER,
        created_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS deals (
        deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        buyer TEXT,
        seller TEXT,
        amount REAL,
        fee REAL,
        description TEXT,
        status TEXT,
        added_by INTEGER,
        closed_by INTEGER,
        created_at INTEGER,
        closed_at INTEGER,
        group_chat_id INTEGER,
        message_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS invite_links (
        invite_link TEXT PRIMARY KEY,
        target_chat_id INTEGER,
        user_id INTEGER,
        created_at INTEGER,
        revoked INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    conn.commit()
    conn.close()

# ----------------- Settings -----------------
def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("REPLACE INTO settings(key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None

# ----------------- Deals -----------------
def add_deal(code: str, buyer: str, seller: str, amount: float, fee: float, description: str, added_by: int, ts: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deals(code, buyer, seller, amount, fee, description, status, added_by, created_at) "
        "VALUES (?,?,?,?,?,?, 'open', ?, ?)",
        (code, buyer, seller, amount, fee, description, added_by, ts)
    )
    conn.commit()
    did = cur.lastrowid
    conn.close()
    return did

def mark_deal_closed(code: str, closed_by: int, ts: int):
    conn = get_conn()
    conn.execute(
        "UPDATE deals SET status='closed', closed_by=?, closed_at=? WHERE code=?",
        (closed_by, ts, code)
    )
    conn.commit()
    conn.close()

def set_deal_message(code: str, group_chat_id: int, message_id: int):
    conn = get_conn()
    conn.execute("UPDATE deals SET group_chat_id=?, message_id=? WHERE code=?", (group_chat_id, message_id, code))
    conn.commit()
    conn.close()

# ----------------- Invite links -----------------
def add_invite_link(link: str, target_chat_id: int, user_id: int, ts: int):
    conn = get_conn()
    conn.execute(
        "REPLACE INTO invite_links(invite_link, target_chat_id, user_id, created_at, revoked) "
        "VALUES (?,?,?,?,0)",
        (link, target_chat_id, user_id, ts)
    )
    conn.commit()
    conn.close()

def mark_invite_revoked(link: str):
    conn = get_conn()
    conn.execute("UPDATE invite_links SET revoked=1 WHERE invite_link=?", (link,))
    conn.commit()
    conn.close()

# ----------------- GBAN -----------------
def add_gban(user_id: int, reason: str, by_id: int, ts: int):
    conn = get_conn()
    conn.execute("REPLACE INTO gban(user_id, reason, by_id, created_at) VALUES (?,?,?,?)", (user_id, reason, by_id, ts))
    conn.commit()
    conn.close()

def remove_gban(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM gban WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_gbanned(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM gban WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(row)
