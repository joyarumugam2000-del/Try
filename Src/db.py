# db.py
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_code TEXT UNIQUE,
    seller_username TEXT,
    buyer_username TEXT,
    amount TEXT,
    details TEXT,
    source_chat_id INTEGER,
    source_message_id INTEGER,
    seller_user_id INTEGER,
    buyer_user_id INTEGER,
    seller_confirmed INTEGER DEFAULT 0,
    buyer_confirmed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', -- pending, posted, closed
    posted_message_id INTEGER,
    posted_at TEXT,
    added_by_admin_id INTEGER,
    added_by_admin_username TEXT,
    closed_by_admin_id INTEGER,
    closed_by_admin_username TEXT,
    closed_at TEXT,
    kick_time TEXT,
    kicked INTEGER DEFAULT 0,
    created_at TEXT
);
"""

def now_iso():
    return datetime.datetime.utcnow().isoformat()

class DB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_TABLE_SQL)
            await db.commit()

    async def create_deal(self, seller_username: str, buyer_username: str, amount: str, details: str,
                          source_chat_id: int, source_message_id: int) -> int:
        created_at = now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO deals (seller_username, buyer_username, amount, details, source_chat_id, source_message_id, created_at) VALUES (?,?,?,?,?,?,?)",
                (seller_username, buyer_username, amount, details, source_chat_id, source_message_id, created_at)
            )
            await db.commit()
            rowid = cursor.lastrowid
            deal_code = f"DVA{rowid}"
            await db.execute("UPDATE deals SET deal_code = ? WHERE id = ?", (deal_code, rowid))
            await db.commit()
            return rowid

    async def get_deal(self, by_id: Optional[int] = None, by_code: Optional[str] = None) -> Optional[dict]:
        q, params = None, None
        if by_id:
            q = "SELECT * FROM deals WHERE id = ?"
            params = (by_id,)
        elif by_code:
            q = "SELECT * FROM deals WHERE deal_code = ?"
            params = (by_code,)
        else:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(q, params)
            row = await cur.fetchone()
            return dict(row) if row else None

    async def confirm_user(self, deal_id: int, role: str, user_id: int, username: str):
        if role not in ("buyer", "seller"):
            return
        col_user_id = f"{role}_user_id"
        col_confirm = f"{role}_confirmed"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE deals SET {col_user_id} = ?, {col_confirm} = 1 WHERE id = ?",
                (user_id, deal_id)
            )
            await db.commit()

    async def set_posted(self, deal_id: int, posted_message_id: int):
        posted_at = now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET status = 'posted', posted_message_id = ?, posted_at = ? WHERE id = ?",
                (posted_message_id, posted_at, deal_id)
            )
            await db.commit()

    async def set_added_by(self, deal_id: int, admin_id: int, admin_username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET added_by_admin_id = ?, added_by_admin_username = ? WHERE id = ?",
                (admin_id, admin_username, deal_id)
            )
            await db.commit()

    async def set_closed(self, deal_id: int, admin_id: int, admin_username: str):
        closed_at = now_iso()
        kick_time = (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET status = 'closed', closed_by_admin_id = ?, closed_by_admin_username = ?, closed_at = ?, kick_time = ? WHERE id = ?",
                (admin_id, admin_username, closed_at, kick_time, deal_id)
            )
            await db.commit()
        return kick_time

    async def get_pending_kicks(self) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM deals WHERE status = 'closed' AND kicked = 0 AND kick_time IS NOT NULL"
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def mark_kicked(self, deal_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE deals SET kicked = 1 WHERE id = ?", (deal_id,))
            await db.commit()

    async def both_confirmed(self, deal_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT buyer_confirmed, seller_confirmed FROM deals WHERE id = ?", (deal_id,))
            row = await cur.fetchone()
            if not row:
                return False
            return bool(row["buyer_confirmed"]) and bool(row["seller_confirmed"])
