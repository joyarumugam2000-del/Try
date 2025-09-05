import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from .config import BOT_TOKEN, OWNER_ID, LOG_CHANNEL_ID
from . import db
from . import utils
from . import deals
from . import anti_scam

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)
log=logging.getLogger("bot")

# ---------------- Inline menu ----------------
async def cmd_start(update: Update, context):
    await update.effective_message.reply_text("Hi! I'm your Anti-Scam + DVA/Escrow bot.\nUse /help for commands")

async def cmd_help(update: Update, context):
    await update.effective_message.reply_text(
        "/start - Menu\n/help - Help\n/form - Start deal form\n/dvaonly - Mark DVA group"
    )

# ---------------- Main ----------------
def main():
    db.init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["OWNER_ID"]=OWNER_ID

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    # Anti-scam
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, anti_scam.on_new_members))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, anti_scam.on_any_message))

    # Deals
    for h in deals.build_handlers():
        app.add_handler(h)

    # Error logging
    async def on_error(update, context):
        log.exception("Update error: %s", context.error)
    app.add_error_handler(on_error)

    log.info("Bot started")
    app.run_polling(close_loop=False)

if __name__=="__main__":
    main()
