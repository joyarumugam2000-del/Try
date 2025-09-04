import random
import string
import time
from telegram.ext import ContextTypes
from telegram import ChatMember

# Generate deal code like DL-ABCDEFGH
def gen_deal_code() -> str:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"DL-{suffix}"

# Current timestamp
def now_ts() -> int:
    return int(time.time())

# Check if user is owner
async def is_owner(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    return str(user_id) == str(context.bot_data.get("OWNER_ID"))

# Check if user is admin in chat
async def is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
    except Exception:
        return False

# Optional: parse @username mentions or IDs
def parse_user_mention(text: str) -> str:
    return text.strip()
