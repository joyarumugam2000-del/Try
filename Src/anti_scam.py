import re
from .db import add_seen_username, is_gbanned

# Normalize username
def skeleton(username: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (username or "").lower())

# Compare usernames
def looks_like(new_username: str, old_username: str, min_similarity: float = 0.8):
    s1 = skeleton(new_username)
    s2 = skeleton(old_username)
    if not s1 or not s2: return False, 0, ""
    matches = sum(c1==c2 for c1,c2 in zip(s1,s2))
    score = matches/max(len(s1),len(s2))
    return score>=min_similarity, score, "Skeleton match" if score>=min_similarity else ""

# New member
async def on_new_members(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    for m in msg.new_chat_members:
        uname = m.username or ""
        sk = skeleton(uname)
        add_seen_username(chat.id, uname, sk, int(msg.date.timestamp()))
        if is_gbanned(m.id):
            try: await context.bot.ban_chat_member(chat.id, m.id)
            except: pass

# Left member
async def on_left_member(update, context):
    pass

# Any message GBAN enforcement
async def on_any_message(update, context):
    user = update.effective_user
    chat = update.effective_chat
    if is_gbanned(user.id):
        try: await context.bot.ban_chat_member(chat.id, user.id)
        except: pass
