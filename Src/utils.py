import random
import string
import time
from telegram.ext import ContextTypes
from telegram import ChatMember

def gen_deal_code() -> str:
    """Generate unique deal code like DL-ABCDEFGH"""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"DL-{suffix}"

def now_ts() -> int:
    """Return current timestamp"""
    return int(time.time())

async def is_owner(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user is bot owner"""
    return str(user_id) == str(context.bot_data.get("OWNER_ID"))

async def is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    """Check if user is admin in chat"""
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
    except Exception:
        return False

def parse_user_mention(text: str) -> str:
    """Clean username or ID"""
    return text.strip()
