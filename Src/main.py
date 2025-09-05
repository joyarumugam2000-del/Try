# main.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from .config import BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID
from . import db
from .anti_scam import on_new_members, on_left_member, on_any_message
from .deals import build_handlers as build_deal_handlers
from .utils import is_admin

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO
)
log = logging.getLogger("bot")

async def log_event(context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = LOG_CHANNEL_ID or int(context.bot_data.get("LOG_CHANNEL_ID", 0) or 0)
    if not chat_id:
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=text[:4096])
    except Exception as e:
        log.warning("Failed to log to channel: %s", e)

# ---------------- Menus ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start a Deal Form", callback_data="menu:form")],
        [InlineKeyboardButton("Help", callback_data="menu:help")],
        [InlineKeyboardButton("Show Commands", callback_data="menu:cmds")]
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
            "Post your deal form in the group:\n\nSeller: @username\nBuyer: @username\nAmount: number\nPayment mode: mode\nDescription: text",
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
            [InlineKeyboardButton("Show Commands", callback_data="menu:cmds")]
        ])
        await q.edit_message_text("Hi! I'm your Anti-Scam + DVA/Escrow bot.\nChoose an option:", reply_markup=kb)

def help_text() -> str:
    return (
        "*Anti-Scam*\n"
        "• Watches joins and flags look-alike usernames.\n"
        "• Admins can Approve/GBAN suspects.\n\n"
        "*DVA/Escrow*\n"
        "• Say 'escrow' or 'dva' in group → get a one-time link.\n"
        "• Post deal form and admin replies 'add' to open deal, 'close' to finish.\n\n"
        "*Global Ban*\n"
        "• Owner can /gban and /ungban users."
    )

def commands_text() -> str:
    return (
        "/start – Menu\n"
        "/help – Help text\n"
        "/form – Start deal form\n"
        "/suspects – Show pending suspects\n"
        "/gban – Owner: global ban user\n"
        "/ungban – Owner: remove global ban\n"
        "/dvaonly – Owner: set DVA group"
    )

# ---------------- Main ----------------
def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN missing. Set in config or .env")

    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["OWNER_ID"] = str(OWNER_ID)
    app.bot_data["LOG_CHANNEL_ID"] = str(LOG_CHANNEL_ID)

    # Init DB
    db.init_db()

    # Basic commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", lambda u,c: u.effective_message.reply_text(help_text(), parse_mode=ParseMode.MARKDOWN)))

    # Inline menu
    app.add_handler(CallbackQueryHandler(cb_menu, pattern=r"^menu:"))

    # Anti-scam handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_any_message))

    # DVA / Deals handlers
    for h in build_deal_handlers():
        app.add_handler(h)

    # Error logging
    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
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
