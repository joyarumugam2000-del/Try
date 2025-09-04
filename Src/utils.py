import re
import string
import random
import time
from datetime import datetime, timezone
from typing import Optional
from telegram.ext import ContextTypes

async def is_owner(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    owner_id = int(context.bot_data.get("OWNER_ID", 0))
    return user_id == owner_id

async def is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        cm = await context.bot.get_chat_member(chat_id, user_id)
        return cm.status in ("administrator", "creator")
    except Exception:
        return False

def now_ts() -> int:
    return int(time.time())

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def gen_deal_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "DL-" + "".join(random.choice(alphabet) for _ in range(8))

def parse_user_mention(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r'@([A-Za-z0-9_]{5,})', text)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{6,})\b', text)
    if m:
        return m.group(1)
    return None
