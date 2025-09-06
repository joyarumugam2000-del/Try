# main.py
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler, CallbackQueryHandler
from utils import parse_form_text, fmt_time_india, now_iso
from db import DB
import logging

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

async def log_to_channel(app, text: str):
    try:
        await app.bot.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        logger.error("Failed to send log: %s", e)

async def handle_group_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # parse only group messages that look like form
    if not update.message or not update.effective_chat:
        return
    text = update.message.text
    parsed = parse_form_text(text)
    if not parsed:
        return
    # create deal in DB
    seller = parsed["seller"]
    buyer = parsed["buyer"]
    amount = parsed["amount"]
    details = parsed["details"]
    source_chat_id = update.effective_chat.id
    source_message_id = update.message.message_id
    deal_row_id = await db.create_deal(seller, buyer, amount, details, source_chat_id, source_message_id)
    deal_code = f"DVA{deal_row_id}"

    # deep links for buyer & seller
    bot_username = (await context.bot.get_me()).username
    # start payload: join:<deal_id>:role  — note: Telegram will URL encode automatically
    buyer_start = f"https://t.me/{bot_username}?start=join:{deal_row_id}:buyer"
    seller_start = f"https://t.me/{bot_username}?start=join:{deal_row_id}:seller"

    text_reply = (
        f"📌 Deal registered (temporary): {deal_code}\n"
        f"Seller: @{seller}\nBuyer: @{buyer}\nAmount: {amount}\n\n"
        "Buyer & Seller — please click the appropriate button below to verify your username privately with the bot and receive the invite link to the DVA group."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="I'm Buyer — Join", url=buyer_start),
         InlineKeyboardButton(text="I'm Seller — Join", url=seller_start)]
    ])
    await update.message.reply_text(text_reply, reply_markup=kb)
    await log_to_channel(context.application, f"[{now_iso()}] New form parsed: {deal_code} seller=@{seller} buyer=@{buyer} amount={amount} details={details}")

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /start deep links like:
    /start join:<deal_id>:buyer
    """
    user = update.effective_user
    text = update.message.text or ""
    parts = text.split()
    payload = parts[1] if len(parts) >= 2 else ""
    if not payload:
        await update.message.reply_text("Welcome to DVA bot. This bot only handles deal flows for DVA groups.")
        return
    # parse expected payload
    try:
        # payload format: join:123:buyer
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

    expected_username = deal[f"{role}_username"] if f"{role}_username" in deal else deal[f"{role}_username"]
    # db fields are buyer_username / seller_username
    expected_username = deal["buyer_username"] if role == "buyer" else deal["seller_username"]

    # Ensure user has a username
    actual_username = user.username
    if not actual_username:
        await update.message.reply_text("You don't have a Telegram username set. Set a username first (@username) and click the button again.")
        return

    if actual_username.lower() != expected_username.lower():
        await update.message.reply_text(
            f"Your @username is @{actual_username} but the deal expects @{expected_username}.\n"
            "If you control that username, change it to match, or ask the person who posted to correct the username."
        )
        await log_to_channel(context.application, f"[{now_iso()}] User @{actual_username} attempted to claim role {role} for deal {deal['deal_code']} (expected @{expected_username})")
        return

    # Mark confirmed
    await db.confirm_user(deal_id, role, user.id, actual_username)
    await update.message.reply_text(f"Thanks @{actual_username}! You are verified as the {role} for deal {deal['deal_code']} — here's the invite link to join the DVA group:\n\n{DVA_INVITE_LINK}\n\nAfter both parties join, the deal will be posted in the DVA group.")
    await log_to_channel(context.application, f"[{now_iso()}] @{actual_username} confirmed as {role} for {deal['deal_code']}")

    # If both confirmed and both are members (or can be checked), we will post once we detect both in DVA group.
    both_confirmed = await db.both_confirmed(deal_id)
    if both_confirmed:
        # check membership of both in DVA group
        buyer_id = deal.get("buyer_user_id")
        seller_id = deal.get("seller_user_id")
        # get the latest deal to obtain user ids that may have been updated by confirm_user
        updated = await db.get_deal(by_id=deal_id)
        buyer_id = updated.get("buyer_user_id")
        seller_id = updated.get("seller_user_id")
        if buyer_id and seller_id:
            # check chat member statuses
            try:
                buyer_status = await context.bot.get_chat_member(DVA_GROUP_ID, buyer_id)
                seller_status = await context.bot.get_chat_member(DVA_GROUP_ID, seller_id)
                buyer_in = buyer_status.status in ("member", "administrator", "creator")
                seller_in = seller_status.status in ("member", "administrator", "creator")
            except Exception:
                buyer_in = seller_in = False
            if buyer_in and seller_in:
                await post_deal_to_dva(context, deal_id)

async def post_deal_to_dva(context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    app = context.application
    deal = await db.get_deal(by_id=deal_id)
    if not deal:
        return
    if deal.get("status") == "posted":
        return
    deal_code = deal["deal_code"]
    amount = deal["amount"]
    details = deal["details"] or "—"
    buyer = deal["buyer_username"]
    seller = deal["seller_username"]
    posted_text = (
        f"🤝 Deal Info\n"
        f"💰 Received: {amount}\n"
        f"🆔 Deal ID: {deal_code}\n"
        f"ℹ️ Details: {details}\n\n"
        f"👤 Buyer: @{buyer}\n"
        f"👨‍💼 Seller: @{seller}\n"
        f"🔐 DVA admin By: (pending admin add; admin use /adddeal to register)\n"
        f"\n⏰ Created: {fmt_time_india(deal['created_at'])}"
    )
    sent = await app.bot.send_message(DVA_GROUP_ID, posted_text)
    await db.set_posted(deal_id, sent.message_id)
    await log_to_channel(app, f"[{now_iso()}] Deal posted in DVA group: {deal_code} buyer=@{buyer} seller=@{seller} amount={amount}")

async def handle_new_members_in_dva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Triggered when new_chat_members join a chat — we check whether they are joining DVA group and if there are pending deals waiting for them
    if not update.message or not update.message.new_chat_members:
        return
    chat = update.effective_chat
    if chat.id != DVA_GROUP_ID:
        return
    joined_ids = [m.id for m in update.message.new_chat_members]
    # fetch closed/pending deals that might be waiting for a join
    # logic: check all pending deals where both confirmed but not posted, and one of joined user IDs equals these.
    # We'll scan recent deals (simple approach)
    # For simplicity: every time a user joins DVA group we check all deals where status != posted and both confirmed are true.
    # If both parties are now present, post the deal.
    async with context.application.bot:
        # Get all deals (could be optimized with a WHERE clause)
        # We'll rely on db and then check get_chat_member for both ids
        # Note: keep limit; here we fetch a batch of deals to avoid scanning huge tables.
        # For simple use, we fetch all deals where status != posted and both confirmed true.
        # We'll query using a small raw SQL inside DB layer for simplicity:
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM deals WHERE status != 'posted' AND buyer_confirmed = 1 AND seller_confirmed = 1")
            rows = await cur.fetchall()
            for row in rows:
                d = dict(row)
                b_id = d.get("buyer_user_id")
                s_id = d.get("seller_user_id")
                if not b_id or not s_id:
                    continue
                try:
                    b_stat = await context.bot.get_chat_member(DVA_GROUP_ID, b_id)
                    s_stat = await context.bot.get_chat_member(DVA_GROUP_ID, s_id)
                    b_in = b_stat.status in ("member", "administrator", "creator")
                    s_in = s_stat.status in ("member", "administrator", "creator")
                except Exception:
                    b_in = s_in = False
                if b_in and s_in:
                    await post_deal_to_dva(context, d["id"])

async def admin_only_check(context: ContextTypes.DEFAULT_TYPE, admin_user_id: int, chat_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, admin_user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def adddeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /adddeal <DVAid>  OR reply to deal message
    if update.effective_chat.id != DVA_GROUP_ID:
        return
    user = update.effective_user
    is_admin = await admin_only_check(context, user.id, DVA_GROUP_ID)
    if not is_admin:
        await update.message.reply_text("Only DVA group admins can use this command.")
        return

    deal_code = None
    if context.args:
        deal_code = context.args[0].strip()
    elif update.message.reply_to_message:
        # try to extract deal_id from replied bot message (search "Deal ID: DVA####")
        text = update.message.reply_to_message.text or ""
        import re
        m = re.search(r"Deal ID:\s*(DVA\d+)", text)
        if m:
            deal_code = m.group(1)

    if not deal_code:
        await update.message.reply_text("Usage: /adddeal <DVAid> or reply to the bot's deal message and run /adddeal")
        return

    deal = await db.get_deal(by_code=deal_code)
    if not deal:
        await update.message.reply_text("Deal not found.")
        return

    await db.set_added_by(deal["id"], user.id, user.username or str(user.id))
    # edit the posted message to include admin
    if deal.get("posted_message_id"):
        try:
            msg = await context.bot.edit_message_text(
                chat_id=DVA_GROUP_ID,
                message_id=deal["posted_message_id"],
                text=(
                    f"🤝 Deal Info\n"
                    f"💰 Received: {deal['amount']}\n"
                    f"🆔 Deal ID: {deal['deal_code']}\n"
                    f"ℹ️ Details: {deal['details'] or '—'}\n\n"
                    f"👤 Buyer: @{deal['buyer_username']}\n"
                    f"👨‍💼 Seller: @{deal['seller_username']}\n"
                    f"🔐 DVA admin By: @{user.username or user.id}\n"
                    f"\n⏰ Created: {fmt_time_india(deal['created_at'])}"
                )
            )
        except Exception as e:
            logger.warning("Failed to edit message: %s", e)
    await update.message.reply_text(f"Deal {deal_code} registered as added by @{user.username or user.id}")
    await log_to_channel(context.application, f"[{now_iso()}] Deal {deal_code} added by @{user.username or user.id}")

async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /close <DVAid> or reply to deal message
    if update.effective_chat.id != DVA_GROUP_ID:
        return
    user = update.effective_user
    is_admin = await admin_only_check(context, user.id, DVA_GROUP_ID)
    if not is_admin:
        await update.message.reply_text("Only DVA group admins can use this command.")
        return

    deal_code = None
    if context.args:
        deal_code = context.args[0].strip()
    elif update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
        import re
        m = re.search(r"Deal ID:\s*(DVA\d+)", text)
        if m:
            deal_code = m.group(1)

    if not deal_code:
        await update.message.reply_text("Usage: /close <DVAid> or reply to the bot's deal message and run /close")
        return

    deal = await db.get_deal(by_code=deal_code)
    if not deal:
        await update.message.reply_text("Deal not found.")
        return

    kick_time = await db.set_closed(deal["id"], user.id, user.username or str(user.id))
    await update.message.reply_text(f"Deal {deal_code} closed by @{user.username or user.id}. Participants will be removed after 15 minutes (at {kick_time} UTC).")
    await log_to_channel(context.application, f"[{now_iso()}] Deal {deal_code} closed by @{user.username or user.id}")

async def kick_worker(app):
    # background loop to check for closed deals due to be kicked
    while True:
        try:
            pending = await db.get_pending_kicks()
            import datetime
            now = datetime.datetime.utcnow()
            for d in pending:
                if not d.get("kick_time"):
                    continue
                kt = datetime.datetime.fromisoformat(d["kick_time"])
                if now >= kt and d.get("kicked") == 0:
                    buyer_id = d.get("buyer_user_id")
                    seller_id = d.get("seller_user_id")
                    # try to kick users (ban then unban quickly)
                    for uid in (buyer_id, seller_id):
                        if not uid:
                            continue
                        try:
                            await app.bot.ban_chat_member(DVA_GROUP_ID, uid)
                            # unban so they may rejoin later
                            await app.bot.unban_chat_member(DVA_GROUP_ID, uid)
                        except Exception as e:
                            logger.warning("Failed to kick user %s for deal %s: %s", uid, d["deal_code"], e)
                    await db.mark_kicked(d["id"])
                    await log_to_channel(app, f"[{now_iso()}] Kicked participants of deal {d['deal_code']}")
        except Exception as e:
            logger.error("Kick worker error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # init db synchronously before start
    import asyncio
    asyncio.get_event_loop().run_until_complete(db.init())

    # handlers
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & filters.Regex(r'(?i)^@admins'), handle_group_form))
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.Chat(DVA_GROUP_ID) & filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members_in_dva))
    application.add_handler(CommandHandler("adddeal", adddeal_cmd))
    application.add_handler(CommandHandler("close", close_cmd))

    # start background worker on post_init
    async def on_startup(app):
        app.create_task(kick_worker(app))

    application.post_init = on_startup

    logger.info("Starting DVA bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
