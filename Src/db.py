import sqlite3
from typing import Optional, Dict, Any, List

DB_PATH = "bot.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Settings
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    
    # Deals
    c.execute("""CREATE TABLE IF NOT EXISTS deals(
        code TEXT PRIMARY KEY,
        buyer TEXT,
        seller TEXT,
        amount REAL,
        fee REAL,
        admin_add TEXT,
        admin_close TEXT,
        ts_added INTEGER,
        ts_closed INTEGER,
        chat_id INTEGER,
        msg_id INTEGER
    )""")
    
    # Invite links
    c.execute("""CREATE TABLE IF NOT EXISTS invite_links(
        link TEXT PRIMARY KEY,
        chat_id INTEGER,
        user_id INTEGER,
        ts INTEGER
    )""")
    
    # Anti-scam seen usernames
    c.execute("""CREATE TABLE IF NOT EXISTS seen_usernames(
        chat_id INTEGER,
        username TEXT,
        skeleton TEXT,
        ts INTEGER
    )""")
    
    # Global ban
    c.execute("""CREATE TABLE IF NOT EXISTS gbans(
        user_id INTEGER PRIMARY KEY
    )""")
    
    conn.commit()
    conn.close()

# ------------------ Settings ------------------
def set_setting(key: str, value: Any):
    conn = get_conn()
    conn.execute("REPLACE INTO settings(key,value) VALUES (?,?)", (key,str(value)))
    conn.commit()
    conn.close()

def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ------------------ Deals ------------------
def add_deal(code, buyer, seller, amount, fee, admin_add, ts_added, chat_id=None, msg_id=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO deals(code,buyer,seller,amount,fee,admin_add,ts_added,chat_id,msg_id) VALUES(?,?,?,?,?,?,?,?,?)",
        (code,buyer,seller,amount,fee,admin_add,ts_added,chat_id,msg_id)
    )
    conn.commit()
    conn.close()

def set_deal_message(code, chat_id, msg_id):
    conn = get_conn()
    conn.execute("UPDATE deals SET chat_id=?, msg_id=? WHERE code=?", (chat_id, msg_id, code))
    conn.commit()
    conn.close()

def mark_deal_closed(code, admin_close):
    import time
    conn = get_conn()
    conn.execute("UPDATE deals SET admin_close=?, ts_closed=? WHERE code=?", (admin_close,int(time.time()),code))
    conn.commit()
    conn.close()

# ------------------ Invite links ------------------
def add_invite_link(link, chat_id, user_id, ts):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO invite_links(link,chat_id,user_id,ts) VALUES(?,?,?,?)", (link,chat_id,user_id,ts))
    conn.commit()
    conn.close()

# ------------------ Anti-scam ------------------
def add_seen_username(chat_id, username, skeleton, ts):
    conn = get_conn()
    conn.execute("INSERT INTO seen_usernames(chat_id,username,skeleton,ts) VALUES(?,?,?,?)", (chat_id,username,skeleton,ts))
    conn.commit()
    conn.close()

# ------------------ Global ban ------------------
def is_gbanned(user_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM gbans WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)

def gban_user(user_id: int):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO gbans(user_id) VALUES(?)", (user_id,))
    conn.commit()
    conn.close()

def ungban_user(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM gbans WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
