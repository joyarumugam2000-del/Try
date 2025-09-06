# main.py
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
)
from Src.utils import parse_form_text, fmt_time_india, now_iso
from Src.db import DB
import logging

# Load environment
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DVA_GROUP_ID = int(os.getenv("DVA_GROUP_ID"))
DVA_INVITE_LINK = os.getenv("DVA_INVITE_LINK")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
DB_PATH = os.getenv("DB_PATH", "./dva.db")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))

db = DB(DB_PATH)

# ----- Logging helper -----
async def log_to_channel(app, text: str):
    try:
        await app.bot.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        logger.error("Failed to send log: %s", e)

# ----- Regex for deal form -----
DEAL_FORM_REGEX = r"(?i)^@admins\s*\n\s*Seller:\s*@\w+\s*\n\s*Buyer:\s*@\w+\s*\n\s*Amount:\s*\d+(\.\d+)?"

# ----- Handle deal form in group -----
async def handle_group_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    text = update.message.text
    parsed = parse_form_text(text)
    if not parsed:
        return

    seller = parsed["seller"]
    buyer = parsed["buyer"]
    amount = parsed["amount"]
    details = parsed["details"]
    source_chat_id = update.effective_chat.id
    source_message_id = update.message.message_id

    # Create deal in DB
    deal_row_id = await db.create_deal(seller, buyer, amount, details, source_chat_id, source_message_id)
    deal_code = f"DVA{deal_row_id}"

    bot_username = (await context.bot.get_me()).username
    buyer_start = f"https://t.me/{bot_username}?start=join:{deal_row_id}:buyer"
    seller_start = f"https://t.me/{bot_username}?start=join:{deal_row_id}:seller"

    text_reply = (
        f"📌 Deal registered (temporary): {deal_code}\n"
        f"Seller: @{seller}\nBuyer: @{buyer}\nAmount: {amount}\n\n"
        "Buyer & Seller — click your respective button below to verify with the bot and receive the DVA group invite link."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="I'm Buyer — Join", url=buyer_start),
         InlineKeyboardButton(text="I'm Seller — Join", url=seller_start)]
    ])
    await update.message.reply_text(text_reply, reply_markup=kb)
    await log_to_channel(context.application, f"[{now_iso()}] New form parsed: {deal_code} seller=@{seller} buyer=@{buyer} amount={amount} details={details}")

# ----- /start handler for deep links -----
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    parts = text.split()
    payload = parts[1] if len(parts) >= 2 else ""

    if not payload:
        await update.message.reply_text("Welcome to DVA bot. This bot handles deal flows for DVA groups only.")
        return

    try:
        tokens = payload.split(":")
        if len(tokens) != 3 or tokens[0] != "join":
            raise ValueError("invalid payload")
        deal_id = int(tokens[1])
        role = tokens[2]
    except Exception:
        await update.message.reply_text("Invalid start payload.")
        return

    deal = await db.get_deal(by_id=deal_id)
    if not deal:
        await update.message.reply_text("Deal not found or expired.")
        return

    expected_username = deal["buyer_username"] if role == "buyer" else deal["seller_username"]
    actual_username = user.username
    if not actual_username:
        await update.message.reply_text("Set a Telegram username first (@username) and click the button again.")
        return

    if actual_username.lower() != expected_username.lower():
        await update.message.reply_text(
            f"Your @username is @{actual_username} but the deal expects @{expected_username}."
        )
        await log_to_channel(context.application, f"[{now_iso()}] @{actual_username} attempted to claim role {role} for deal {deal['deal_code']}")
        return

    await db.confirm_user(deal_id, role, user.id, actual_username)
    await update.message.reply_text(
        f"Thanks @{actual_username}! You are verified as the {role} for deal {deal['deal_code']}.\n"
        f"Here is the invite link to join the DVA group:\n{DVA_INVITE_LINK}"
    )
    await log_to_channel(context.application, f"[{now_iso()}] @{actual_username} confirmed as {role} for {deal['deal_code']}")

    # Check if both confirmed to post deal
    both_confirmed = await db.both_confirmed(deal_id)
    if both_confirmed:
        updated = await db.get_deal(by_id=deal_id)
        buyer_id = updated.get("buyer_user_id")
        seller_id = updated.get("seller_user_id")
        if buyer_id and seller_id:
            try:
                buyer_status = await context.bot.get_chat_member(DVA_GROUP_ID, buyer_id)
                seller_status = await context.bot.get_chat_member(DVA_GROUP_ID, seller_id)
                if buyer_status.status in ("member", "administrator", "creator") and seller_status.status in ("member", "administrator", "creator"):
                    await post_deal_to_dva(context, deal_id)
            except Exception:
                pass

# ----- Post deal in DVA group -----
async def post_deal_to_dva(context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    app = context.application
    deal = await db.get_deal(by_id=deal_id)
    if not deal or deal.get("status") == "posted":
        return

    posted_text = (
        f"🤝 Deal Info\n"
        f"💰 Received: {deal['amount']}\n"
        f"🆔 Deal ID: {deal['deal_code']}\n"
        f"ℹ️ Details: {deal['details'] or '—'}\n\n"
        f"👤 Buyer: @{deal['buyer_username']}\n"
        f"👨‍💼 Seller: @{deal['seller_username']}\n"
        f"🔐 DVA admin By: (pending admin add)\n"
        f"\n⏰ Created: {fmt_time_india(deal['created_at'])}"
    )
    sent = await app.bot.send_message(DVA_GROUP_ID, posted_text)
    await db.set_posted(deal_id, sent.message_id)
    await log_to_channel(app, f"[{now_iso()}] Deal posted: {deal['deal_code']}")

# ----- Main function -----
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Init DB
    asyncio.get_event_loop().run_until_complete(db.init())

    # Handlers
    application.add_handler(MessageHandler(
        filters.ChatType.GROUP & filters.TEXT & filters.Regex(DEAL_FORM_REGEX),
        handle_group_form
    ))
    application.add_handler(CommandHandler("start", start_handler))
    # You can add /adddeal, /close, new member handlers here as before

    # Background kick worker
    async def on_startup(app):
        async def kick_worker(app):
            while True:
                try:
                    pending = await db.get_pending_kicks()
                    import datetime
                    now = datetime.utcnow()
                    for d in pending:
                        if not d.get("kick_time"):
                            continue
                        kt = datetime.fromisoformat(d["kick_time"])
                        if now >= kt and d.get("kicked") == 0:
                            for uid in (d.get("buyer_user_id"), d.get("seller_user_id")):
                                if not uid:
                                    continue
                                try:
                                    await app.bot.ban_chat_member(DVA_GROUP_ID, uid)
                                    await app.bot.unban_chat_member(DVA_GROUP_ID, uid)
                                except Exception as e:
                                    logger.warning("Failed to kick user %s: %s", uid, e)
                            await db.mark_kicked(d["id"])
                            await log_to_channel(app, f"[{now_iso()}] Kicked participants of deal {d['deal_code']}")
                except Exception as e:
                    logger.error("Kick worker error: %s", e)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        app.create_task(kick_worker(app))

    application.post_init = on_startup
    logger.info("Starting DVA bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
