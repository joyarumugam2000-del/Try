"""
db.py - SQLite persistence for forms and deals
"""

import sqlite3
import threading
from typing import Optional, Dict, Any, List


class DB:
    def __init__(self, path: str = "escrow_bot.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS forms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    message_id INTEGER,
                    form_type TEXT,
                    buyer TEXT,
                    seller TEXT,
                    amount REAL,
                    purpose TEXT,
                    filler_id INTEGER,
                    filler_username TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'pending',
                    accepted_by_id INTEGER,
                    accepted_by_username TEXT,
                    accepted_at TEXT,
                    deal_id INTEGER,
                    closed_at TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    form_id INTEGER,
                    chat_id INTEGER,
                    admin_id INTEGER,
                    admin_username TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT,
                    closed_at TEXT
                )
                """
            )
            self.conn.commit()

    def create_form(self, chat_id: int, message_id: int, form_type: str, buyer: str, seller: str, amount: float, purpose: str, filler_id: int, filler_username: str, created_at: str) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO forms (chat_id, message_id, form_type, buyer, seller, amount, purpose, filler_id, filler_username, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (chat_id, message_id, form_type, buyer, seller, amount, purpose, filler_id, filler_username, created_at),
            )
            self.conn.commit()
            return cur.lastrowid

    def update_form_message_id(self, form_id: int, message_id: int):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE forms SET message_id = ? WHERE id = ?", (message_id, form_id))
            self.conn.commit()

    def get_form(self, form_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_form_by_message(self, chat_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM forms WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_form_accept(self, form_id: int, admin_id: int, admin_username: str, accepted_at: str, deal_id: int):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE forms SET status = 'accepted', accepted_by_id = ?, accepted_by_username = ?, accepted_at = ?, deal_id = ? WHERE id = ?",
                (admin_id, admin_username, accepted_at, deal_id, form_id),
            )
            self.conn.commit()

    def update_form_closed(self, form_id: int, closed_at: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE forms SET status = 'closed', closed_at = ? WHERE id = ?", (closed_at, form_id))
            self.conn.commit()

    def add_deal(self, form_id: int, admin_id: int, admin_username: str, created_at: str) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT chat_id FROM forms WHERE id = ?", (form_id,))
            row = cur.fetchone()
            chat_id = row[0] if row else None
            cur.execute("INSERT INTO deals (form_id, chat_id, admin_id, admin_username, created_at) VALUES (?,?,?,?,?)",
                        (form_id, chat_id, admin_id, admin_username, created_at))
            self.conn.commit()
            return cur.lastrowid

    def get_deal_by_form(self, form_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM deals WHERE form_id = ?", (form_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def close_deal(self, deal_id: int, closed_at: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE deals SET status = 'closed', closed_at = ? WHERE id = ?", (closed_at, deal_id))
            self.conn.commit()

    def list_forms(self, chat_id: int) -> List[Dict[str, Any]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM forms WHERE chat_id = ? AND status = 'pending'", (chat_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def list_deals(self, chat_id: int) -> List[Dict[str, Any]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM deals WHERE chat_id = ?", (chat_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
