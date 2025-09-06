# utils.py
import re
from typing import Optional, Dict
import pytz
import datetime
from dotenv import load_dotenv
import os

load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
tz = pytz.timezone(TIMEZONE)

USERNAME_RE = re.compile(r'@?([A-Za-z0-9_]{3,32})')  # Telegram username constraints (approx)

def parse_form_text(text: str) -> Optional[Dict[str,str]]:
    """
    Parse the group form. Expects text containing:
    @admins
    Seller: @sellername
    Buyer: @buyername
    Amount: 100
    More details : optional text (optional)
    """
    if not text:
        return None
    # Normalize lines
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    joined = "\n".join(lines)
    # quick presence check
    if not joined.lower().startswith("@admins"):
        return None

    # Try extract fields with case-insensitive labels
    seller = _extract_label_value(joined, r"seller\s*:\s*(.+)")
    buyer = _extract_label_value(joined, r"buyer\s*:\s*(.+)")
    amount = _extract_label_value(joined, r"amount\s*:\s*(.+)")
    details = _extract_label_value(joined, r"more details\s*:\s*(.+)") or ""

    if not seller or not buyer or not amount:
        return None

    seller_username = _extract_username(seller)
    buyer_username = _extract_username(buyer)
    if not seller_username or not buyer_username:
        return None

    return {
        "seller": seller_username,
        "buyer": buyer_username,
        "amount": amount.strip(),
        "details": details.strip(),
    }

def _extract_label_value(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def _extract_username(value: str) -> Optional[str]:
    m = USERNAME_RE.search(value)
    return m.group(1) if m else None

def fmt_time_india(iso_utc: str) -> str:
    dt = datetime.datetime.fromisoformat(iso_utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    india = dt.astimezone(tz)
    return india.strftime("%Y-%m-%d %H:%M:%S %Z")

def now_iso():
    return datetime.datetime.utcnow().isoformat()
