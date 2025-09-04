import re
from typing import Tuple
from . import db

# ----------------- Anti-Scam Utilities -----------------
def skeleton(username: str) -> str:
    """
    Normalize a username for look-alike comparison.
    Lowercase, remove non-alphanumeric characters.
    """
    return re.sub(r'[^a-z0-9]', '', (username or "").lower())

def looks_like(new_username: str, old_username: str, min_similarity: float = 0.8) -> Tuple[bool, float, str]:
    """
    Compare two usernames and return if they look similar.
    Returns (is_suspect, similarity_score, reason)
    """
    s1 = skeleton(new_username)
    s2 = skeleton(old_username)
    if not s1 or not s2:
        return False, 0.0, ""
    matches = sum(c1 == c2 for c1, c2 in zip(s1, s2))
    max_len = max(len(s1), len(s2))
    score = matches / max_len if max_len else 0.0
    reason = "Skeleton match" if score >= min_similarity else ""
    return score >= min_similarity, score, reason

# ----------------- Handlers -----------------
async def on_new_members(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    ts = int(update.effective_message.date.timestamp())

    # Register group in DB
    try:
        conn = db.get_conn()
        conn.execute("REPLACE INTO groups(chat_id, title) VALUES (?,?)", (chat.id, chat.title or ""))
        conn.commit()
        conn.close()
    except Exception:
        pass

    for m in msg.new_chat_members:
        uname = m.username or ""
        sk = skeleton(uname)
        db.add_user_profile(m.id, uname, m.first_name or "", m.last_name or "", sk, ts)
        db.add_seen_username(chat.id, uname, sk, ts)

        # GBAN enforcement
        if db.is_gbanned(m.id):
            try:
                await context.bot.ban_chat_member(chat.id, m.id)
            except Exception:
                pass

        # Compare against seen usernames
        seen = db.iter_seen_skeletons(chat.id)
        best_score = 0
        best_match = None
        for row in seen:
            prev_un = row["username"]
            if not prev_un or prev_un.lower() == uname.lower():
                continue
            is_sus, score, reason = looks_like(uname, prev_un)
            if is_sus and score >= best_score:
                best_score, best_match = score, (prev_un, reason)

        if best_match:
            matched, reason = best_match
            sid = db.add_suspect(chat.id, m.id, uname, matched, int(best_score*100), reason, ts)
            # You can add InlineKeyboardMarkup here for admin approve/GBAN if needed

async def on_left_member(update, context):
    msg = update.effective_message
    user = msg.left_chat_member
    if not user:
        return
    ts = int(update.effective_message.date.timestamp())
    db.add_user_profile(user.id, user.username or "", user.first_name or "", user.last_name or "", skeleton(user.username or ""), ts)

async def on_any_message(update, context):
    msg = update.effective_message
    user = msg.from_user
    chat = update.effective_chat
    if db.is_gbanned(user.id):
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
        except Exception:
            pass
