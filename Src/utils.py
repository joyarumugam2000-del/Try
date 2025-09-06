"""
utils.py - small helpers
"""

import datetime
from . import config as cfg


def now_iso():
    # UTC timestamps formatted for readability
    return datetime.datetime.utcnow().strftime(cfg.TIME_FORMAT)


async def is_user_admin(bot, chat_id: int, user_id: int) -> bool:
    """
    Return True if user is an admin or creator in the chat.
    """
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def shorten_username(u: str, keep_front: int = 3, keep_back: int = 2) -> str:
    """
    Shorten @username to style like @T...x if it's long.
    If username is short, returns as-is.
    """
    if not u or not u.startswith("@"):
        return u
    name = u[1:]
    if len(name) <= (keep_front + keep_back + 1):
        return u
    return "@" + name[:keep_front] + "..." + name[-keep_back:]
