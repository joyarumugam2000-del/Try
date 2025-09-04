import sqlite3
from typing import Optional, List
from .config import DB_PATH

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
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
            buyer_id INTEGER,
            seller_id INTEGER,
            amount REAL,
            fee REAL,
            status TEXT,
            created_by INTEGER,
            created_at INTEGER,
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
        """
    )
    conn.commit()
    conn.close()

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

def add_seen_username(chat_id: int, username: str, skeleton: str, ts: int):
    conn = get_conn()
    conn.execute(
        "REPLACE INTO seen_usernames(chat_id, username, skeleton, last_seen) VALUES (?,?,?,?)",
        (chat_id, username or "", skeleton or "", ts),
    )
    conn.commit()
    conn.close()

def iter_seen_skeletons(chat_id: int) -> List[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, skeleton, last_seen FROM seen_usernames WHERE chat_id=?", (chat_id,)
    ).fetchall()
    conn.close()
    return rows

def add_user_profile(user_id: int, username: str, first_name: str, last_name: str, skeleton: str, ts: int):
    conn = get_conn()
    conn.execute(
        "REPLACE INTO users(user_id, username, first_name, last_name, skeleton, last_seen) VALUES (?,?,?,?,?,?)",
        (user_id, username or "", first_name or "", last_name or "", skeleton or "", ts),
    )
    conn.commit()
    conn.close()

def add_suspect(chat_id: int, user_id: int, username: str, matched_username: str, score: int, reason: str, ts: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO suspects(chat_id, user_id, username, matched_username, score, reason, created_at) VALUES (?,?,?,?,?,?,?)",
        (chat_id, user_id, username or "", matched_username or "", score, reason, ts),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid

def set_suspect_status(suspect_id: int, status: str, decided_by: int):
    conn = get_conn()
    conn.execute("UPDATE suspects SET status=?, decided_by=? WHERE id=?", (status, decided_by, suspect_id))
    conn.commit()
    conn.close()

def list_pending_suspects(chat_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM suspects WHERE chat_id=? AND status='pending' ORDER BY created_at DESC LIMIT 50", (chat_id,)
    ).fetchall()
    conn.close()
    return rows

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

def add_deal(code: str, buyer_id: int, seller_id: int, amount: float, fee: float, created_by: int, ts: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deals(code, buyer_id, seller_id, amount, fee, status, created_by, created_at) VALUES (?,?,?,?,?,'open',?,?)",
        (code, buyer_id, seller_id, amount, fee, created_by, ts),
    )
    conn.commit()
    did = cur.lastrowid
    conn.close()
    return did

def mark_deal_closed(code: str):
    conn = get_conn()
    conn.execute("UPDATE deals SET status='closed' WHERE code=?", (code,))
    conn.commit()
    conn.close()

def set_deal_message(code: str, group_chat_id: int, message_id: int):
    conn = get_conn()
    conn.execute("UPDATE deals SET group_chat_id=?, message_id=? WHERE code=?", (group_chat_id, message_id, code))
    conn.commit()
    conn.close()

def add_invite_link(link: str, target_chat_id: int, user_id: int, ts: int):
    conn = get_conn()
    conn.execute(
        "REPLACE INTO invite_links(invite_link, target_chat_id, user_id, created_at, revoked) VALUES (?,?,?,?,0)",
        (link, target_chat_id, user_id, ts),
    )
    conn.commit()
    conn.close()

def mark_invite_revoked(link: str):
    conn = get_conn()
    conn.execute("UPDATE invite_links SET revoked=1 WHERE invite_link=?", (link,))
    conn.commit()
    conn.close()
