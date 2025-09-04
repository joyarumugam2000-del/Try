import logging
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

from .config import BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID, MIN_SIMILARITY
from . import db
from .anti_scam import skeleton, looks_like
from .deals import build_handlers as build_deal_handlers, _send_dva_link
from .utils import now_ts, is_admin, is_owner, parse_user_mention

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

# ----------------- Logging -----------------
async def log_event(context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = LOG_CHANNEL_ID or int(context.bot_data.get("LOG_CHANNEL_ID", 0) or 0)
    if not chat_id:
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=text[:4096])
    except Exception as e:
        log.warning("Failed to log to channel: %s", e)

# ----------------- Inline Menus -----------------
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
        await q.edit_message_text(
            "Use /form here to start a deal form.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="menu:main")]])
        )
    elif key == "help":
        await q.edit_message_text(
            help_text(),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="menu:main")]])
        )
    elif key == "cmds":
        await q.edit_message_text(
            commands_text(),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="menu:main")]])
        )
    elif key == "main":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Start a Deal Form", callback_data="menu:form")],
            [InlineKeyboardButton("Help", callback_data="menu:help")],
            [InlineKeyboardButton("Show Commands", callback_data="menu:cmds")],
        ])
        await q.edit_message_text("Hi! I'm your Anti-Scam + DVA/Escrow bot.\nChoose an option:", reply_markup=kb)

def help_text() -> str:
    return (
        "*Anti-Scam*\n"
        "• I watch joins and flag look-alike usernames for admin review.\n"
        "• Admins can Approve/GBAN suspects.\n\n"
        "*DVA/Escrow*\n"
        "• Say 'escrow' or 'dva' in any group → I'll DM you a one-time invite link.\n"
        "• Use /form to submit buyer, seller, amount (1% fee auto-calculated).\n"
        "• Admin replies 'add' to open the deal, 'close' to close it.\n\n"
        "*Global Ban*\n"
        "• Owner can /gban (reply) and /ungban users."
    )

def commands_text() -> str:
    return (
        "/start – Menu\n"
        "/help – This help\n"
        "/form – Start a deal form\n"
        "/suspects – Show pending username look-alike suspects (admins)\n"
        "/gban – (Owner) Reply or pass @user/ID to add a global ban\n"
        "/ungban – (Owner) Remove a global ban\n"
        "/dvaonly – (Owner) Run inside your DVA group to mark it"
    )

# ----------------- DVA/Escrow inline -----------------
async def on_dva_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or msg.chat.type == "private":
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Get DVA/Escrow Link", callback_data=f"dva_pm:{msg.from_user.id}")]
    ])
    await msg.reply_text("Click below to get a one-time DVA link in PM:", reply_markup=kb)

async def cb_dva_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, user_id_str = q.data.split(":")
    user_id = int(user_id_str)
    if q.from_user.id != user_id:
        await q.answer("This button is not for you.", show_alert=True)
        return
    link = await _send_dva_link(context, user_id)
    if link:
        await q.edit_message_text("✅ Check your PM for the one-time DVA/Escrow link.")
    else:
        await q.edit_message_text("DVA/Escrow group not configured. Ask the owner to run /dvaonly.")

# ----------------- Main -----------------
def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Put it in config or .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Store bot owner & log channel
    app.bot_data["OWNER_ID"] = str(OWNER_ID)
    app.bot_data["LOG_CHANNEL_ID"] = str(LOG_CHANNEL_ID)

    # Init DB
    db.init_db()

    # Basic commands & menu
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", lambda u,c: u.effective_message.reply_text(help_text(), parse_mode=ParseMode.MARKDOWN)))

    # Suspect / GBAN commands
    from .suspects import cmd_suspects, cb_suspect
    app.add_handler(CommandHandler("suspects", cmd_suspects))
    app.add_handler(CallbackQueryHandler(cb_suspect, pattern=r"^suspect:\d+:(approve|gban)$"))

    from .gban import cmd_gban, cmd_ungban
    app.add_handler(CommandHandler("gban", cmd_gban))
    app.add_handler(CommandHandler("ungban", cmd_ungban))

    # DVA/Escrow
    app.add_handler(MessageHandler(filters.Regex(r"(?i)\b(dva|escrow)\b"), on_dva_request))
    app.add_handler(CallbackQueryHandler(cb_dva_pm, pattern=r"^dva_pm:\d+$"))

    # Add Deal Conversation Handlers
    for h in build_deal_handlers():
        app.add_handler(h)

    # New / left members
    from .anti_scam import on_new_members, on_left_member, on_any_message
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))

    # Enforce GBAN on any message
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_any_message))

    # Inline menu
    app.add_handler(CallbackQueryHandler(cb_menu, pattern=r"^menu:"))

    # Error handler
    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("Update error: %s", context.error)
        try:
            await log_event(context, f"❌ Error: {context.error}")
        except Exception:
            pass
    app.add_error_handler(on_error)

    log.info("Bot starting...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
