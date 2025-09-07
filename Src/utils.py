import random
import string
import asyncio
from typing import Iterable, Optional

def generate_deal_id(length: int = 6) -> str:
    """Return a short random ID (A-Z0-9)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def parse_form_text(text: str):
    """
    Robust parser for forms like:
      @admins
      Seller: @joytuwa
      Buyer: @Bacardi_Killer
      Amount: 100
      More details: testing

    Returns dict with keys: seller (username, no @), buyer (username, no @),
    amount (int), details (string or None).

    Raises ValueError if seller/buyer/amount missing or amount invalid.
    """
    data = {"seller": None, "buyer": None, "amount": None, "details": None}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("seller:"):
            data["seller"] = line.split(":", 1)[1].strip().lstrip("@")
        elif lower.startswith("buyer:"):
            data["buyer"] = line.split(":", 1)[1].strip().lstrip("@")
        elif lower.startswith("amount:"):
            raw = line.split(":", 1)[1].strip()
            try:
                data["amount"] = int(raw)
            except ValueError:
                raise ValueError(f"Invalid amount value: {raw}")
        elif lower.startswith("more details:") or lower.startswith("details:"):
            data["details"] = line.split(":", 1)[1].strip()

    if not data["seller"] or not data["buyer"] or data["amount"] is None:
        raise ValueError("Invalid form: missing seller, buyer, or amount")

    return data


async def resolve_user_to_id(bot, user) -> Optional[int]:
    """
    Resolve a user identifier (int id, numeric string, username with/without @)
    to a numeric Telegram user id.

    - If `user` is int -> returns it.
    - If `user` is a numeric string -> returns int(user).
    - If `user` is a username string -> attempts `await bot.get_chat('@username')` and returns chat.id.
    - Returns None if resolution fails.

    NOTE: `bot.get_chat` will succeed only if the username is public or bot has a relation.
    """
    if user is None:
        return None

    # already an int
    if isinstance(user, int):
        return user

    u = str(user).strip()
    # numeric string
    if u.isdigit():
        try:
            return int(u)
        except ValueError:
            return None

    # treat as username
    if not u.startswith("@"):
        u = "@" + u

    try:
        chat = await bot.get_chat(u)   # may raise if username not resolvable
        return int(chat.id)
    except Exception:
        return None


async def kick_users_after_delay(bot, group_id, users: Iterable, delay: int = 1800, *, silent: bool = True):
    """
    Wait `delay` seconds then attempt to ban/kick each user in `users`.

    `users` may be ints, numeric strings, or usernames (with/without '@').
    Unresolvable users are skipped (no crash). Errors are caught per-user.

    If you want logging for failures, set `silent=False` and implement logging in the except blocks
    (or send to a configured LOG_CHANNEL elsewhere).
    """
    await asyncio.sleep(delay)

    for user in users:
        try:
            uid = await resolve_user_to_id(bot, user)
            if uid is None:
                if not silent:
                    try:
                        await bot.send_message(group_id, f"⚠️ Could not resolve user: {user}")
                    except Exception:
                        pass
                continue

            # ban_chat_member is the modern PTB method; it's async
            try:
                await bot.ban_chat_member(chat_id=group_id, user_id=uid)
            except Exception as e:
                # couldn't ban (maybe bot is not admin) — optionally log
                if not silent:
                    try:
                        await bot.send_message(group_id, f"⚠️ Failed to kick user id {uid}: {e}")
                    except Exception:
                        pass
                continue

        except Exception:
            # Defensive: isolate per-user errors so one failure doesn't stop the loop
            continue
