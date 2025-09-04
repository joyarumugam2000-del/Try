import logging
from typing import List, Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from .config import BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, MIN_SIMILARITY
from . import db
from .anti_scam import skeleton, looks_like, normalize_username
from .deals import build_handlers as build_deal_handlers
from .utils import now_ts, is_admin, is_owner, parse_user_mention

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

# ------------- Logging helper -------------
async def log_event(context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = LOG_CHANNEL_ID or int(context.bot_data.get("LOG_CHANNEL_ID", 0) or 0)
    if not chat_id:
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=text[:4096])
    except Exception as e:
        log.warning("Failed to log to channel: %s", e)

# ------------- Core commands -------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start a Deal Form", callback_data="menu:form")],
        [InlineKeyboardButton("Help", callback_data="menu:help")],
        [InlineKeyboardButton("Show Commands", callback_data="menu:cmds")],
    ])
    await update.effective_message.reply_text(
        "Hi! I'm your Anti-Scam + DVA/Escrow bot.\nChoose an option:",
        reply_markup=kb
    )

async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.split(":", 1)[1]
    if key == "form":
        await q.edit_message_text("Use /form here to start a deal form.")
    elif key == "help":
        await q.edit_message_text(help_text())
    elif key == "cmds":
        await q.edit_message_text(commands_text())

def help_text() -> str:
    return (
        "*Anti-Scam*\n"
        "• I watch joins and flag look-alike usernames for admin review.\n"
        "• Admins can Approve/GBAN suspects.\n\n"
        "*DVA/Escrow*\n"
        "• Say 'escrow' or 'dva' in any group → I'll DM you a one-time invite link to the DVA room.\n"
        "• Use /form to submit buyer, seller, amount (1% fee auto-calculated).\n"
        "• Admin replies 'add' to open the deal, 'close' to close it.\n\n"
        "*Global Ban*\n"
        "• Owner can /gban (reply) and /ungban users.\n"
    )

def commands_text() -> str:
    return (
        "/start – Menu\n"
        "/help – This help\n"
        "/form – Start a deal form\n"
        "/suspects – Show pending username look-alike suspects (admins)\n"
        "/gban – (Owner) Reply or pass @user/ID to add a global ban\n"
        "/ungban – (Owner) Remove a global ban\n"
        "/dvaonly – (Owner) Run inside your DVA group to mark it\n    "
    )

# ------------- Username anti-scam on join -------------
async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    ts = now_ts()
    # register group in DB
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

        # GBAN enforcement on join
        from .db import is_gbanned, add_suspect
        if is_gbanned(m.id):
            try:
                await context.bot.ban_chat_member(chat.id, m.id)
                await log_event(context, f"🚫 GBAN enforced: {m.id} in {chat.title} ({chat.id})")
                continue
            except Exception:
                pass

        # Compare against seen usernames for this chat
        seen = db.iter_seen_skeletons(chat.id)
        from .config import MIN_SIMILARITY
        best_score = 0
        best_match = None
        for row in seen:
            prev_un = row["username"]
            if not prev_un or prev_un.lower() == uname.lower():
                continue
            is_sus, score, reason = looks_like(uname, prev_un, MIN_SIMILARITY)
            if is_sus and score >= best_score:
                best_score, best_match = score, (prev_un, reason)

        if best_match:
            matched, reason = best_match
            sid = db.add_suspect(chat.id, m.id, uname, matched, best_score, reason, ts)
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Approve", callback_data=f"suspect:{sid}:approve"),
                    InlineKeyboardButton("GBAN", callback_data=f"suspect:{sid}:gban"),
                ]
            ])
            await msg.reply_text(
                f"⚠️ Possible look-alike username:\n"
                f"New: @{uname}\nLooks like: @{matched}\nScore: {best_score} ({reason})",
                reply_markup=kb
            )
            await log_event(context, f"👀 Suspect {m.id} @{uname} ~ @{matched} score={best_score} in {chat.title}")

async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = msg.left_chat_member
    if not user:
        return
    db.add_user_profile(user.id, user.username or "", user.first_name or "", user.last_name or "", skeleton(user.username or ""), now_ts())

async def cb_suspect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, sid, action = q.data.split(":")
    sid = int(sid)
    rows = db.get_conn().execute("SELECT * FROM suspects WHERE id=?", (sid,)).fetchall()
    if not rows:
        await q.edit_message_text("This suspect entry no longer exists.")
        return
    row = rows[0]
    chat_id = row["chat_id"]
    user_id = row["user_id"]
    if not (await is_owner(context, q.from_user.id) or await is_admin(context, chat_id, q.from_user.id)):
        await q.answer("Admins only.", show_alert=True)
        return

    if action == "approve":
        db.set_suspect_status(sid, "approved", q.from_user.id)
        await q.edit_message_text(q.message.text + "\n\n✅ Approved by admin.")
        await log_event(context, f"✅ Approved suspect {user_id} in {chat_id}")
    elif action == "gban":
        from .db import add_gban
        db.set_suspect_status(sid, "gbanned", q.from_user.id)
        add_gban(user_id, "Look-alike username scam", q.from_user.id, now_ts())
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
        except Exception:
            pass
        await q.edit_message_text(q.message.text + "\n\n🚫 GBANNED by admin.")
        await log_event(context, f"🚫 GBAN suspect {user_id} from {chat_id}")

async def cmd_suspects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not await is_admin(context, chat_id, update.effective_user.id):
        return
    rows = db.list_pending_suspects(chat_id)
    if not rows:
        await update.effective_message.reply_text("No pending suspects for this group.")
        return
    lines = []
    for r in rows[:20]:
        lines.append(f"#{r['id']} @{r['username']} ~ @{r['matched_username']} score={r['score']} ({r['reason']})")
    await update.effective_message.reply_text("\n".join(lines)[:4096])

# ------------- GBAN -------------
async def find_user_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int, token: str) -> Optional[int]:
    token = token.strip()
    if token.isdigit():
        return int(token)
    if token.startswith("@"):
        token = token[1:]
    return None

async def cmd_gban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(context, update.effective_user.id):
        return
    reason = " ".join(context.args) if context.args else "Manual GBAN"
    target_id = None
    if update.effective_message.reply_to_message:
        target_id = update.effective_message.reply_to_message.from_user.id
    else:
        token = parse_user_mention(update.effective_message.text or "")
        if token:
            target_id = await find_user_id(context, update.effective_chat.id, token)
    if not target_id:
        await update.effective_message.reply_text("Reply to a user's message or pass @username/ID to GBAN.")
        return
    from .db import add_gban
    add_gban(target_id, reason, update.effective_user.id, now_ts())
    await update.effective_message.reply_text(f"🚫 GBANNED {target_id}. Reason: {reason}")
    await log_event(context, f"🚫 GBAN {target_id} by {update.effective_user.id}. Reason: {reason}")

async def cmd_ungban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner(context, update.effective_user.id):
        return
    target_id = None
    if update.effective_message.reply_to_message:
        target_id = update.effective_message.reply_to_message.from_user.id
    else:
        token = parse_user_mention(update.effective_message.text or "")
        if token and token.isdigit():
            target_id = int(token)
    if not target_id:
        await update.effective_message.reply_text("Reply to a user's message or pass a numeric ID to UNGBAN.")
        return
    from .db import remove_gban
    remove_gban(target_id)
    await update.effective_message.reply_text(f"Removed GBAN for {target_id}.")
    await log_event(context, f"♻️ UNGBAN {target_id} by {update.effective_user.id}")

# ------------- Message enforcement (GBAN on speak) -------------
async def on_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = msg.from_user
    chat = update.effective_chat
    from .db import is_gbanned
    if is_gbanned(user.id):
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
            await log_event(context, f"🚫 GBAN enforced on message: {user.id} in {chat.title} ({chat.id})")
        except Exception:
            pass

# ------------- Error handler -------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Update error: %s", context.error)
    try:
        await log_event(context, f"❌ Error: {context.error}")
    except Exception:
        pass

# ------------- App bootstrap -------------
def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Put it in .env")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.bot_data["OWNER_ID"] = str(OWNER_ID)
    app.bot_data["LOG_CHANNEL_ID"] = str(LOG_CHANNEL_ID)

    db.init_db()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", lambda u,c: u.effective_message.reply_text(help_text(), parse_mode=ParseMode.MARKDOWN)))
    app.add_handler(CommandHandler("suspects", cmd_suspects))
    app.add_handler(CommandHandler("gban", cmd_gban))
    app.add_handler(CommandHandler("ungban", cmd_ungban))

    app.add_handler(CallbackQueryHandler(cb_menu, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(cb_suspect, pattern=r"^suspect:\d+:(approve|gban)$"))

    for h in build_deal_handlers():
        app.add_handler(h)

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))

    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_any_message))

    app.add_error_handler(on_error)

    log.info("Bot starting...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
