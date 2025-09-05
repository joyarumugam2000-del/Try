import random
import string
import time
import re
from telegram import ChatMember
from telegram.ext import ContextTypes
from .config import ESCROW_FEE_RATE  # Define 0.01 in config if not already

# --- Generate unique deal code like DL-ABCDEFGH ---
def gen_deal_code() -> str:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"DL-{suffix}"

# --- Current timestamp ---
def now_ts() -> int:
    return int(time.time())

# --- Check if user is the bot owner ---
async def is_owner(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    return str(user_id) == str(context.bot_data.get("OWNER_ID"))

# --- Check if user is admin in a chat ---
async def is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
    except Exception:
        return False

# --- Parse @username or ID text ---
def parse_user_mention(text: str) -> str:
    return text.strip()

# --- Validate username format ---
def is_valid_username(username: str) -> bool:
    return bool(re.match(r"^@[\w\d_]{5,32}$", username))

# --- Calculate DVA/Escrow fee based on amount ---
def calc_fee(amount: float) -> float:
    return round(amount * ESCROW_FEE_RATE, 2)

# --- Optional helper to kick user from chat ---
async def kick_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    try:
        await context.bot.ban_chat_member(chat_id, user_id)
    except Exception as e:
        print(f"Failed to kick user {user_id}: {e}")
