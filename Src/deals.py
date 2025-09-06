from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
from . import config as cfg
from .db import DB
import re

db = DB(cfg.DB_PATH)

# ---------------------------
# /add command: start a deal
# ---------------------------
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_id = user.id

    # Check if replied to a message
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    elif context.args:
        deal_id = context.args[0]
        text = db.get_form_by_id(deal_id)
        if not text:
            await update.message.reply_text("❌ No form found with that ID.")
            return
    else:
        await update.message.reply_text("❌ Reply to a form message or provide deal ID.")
        return

    # Extract details from form (simple regex, adjust as needed)
    match = re.search(r"✅👤 BUYER: (@\S+)\s+SELLER: (@\S+)\s+AMOUNT: (\d+)", text)
    if not match:
        await update.message.reply_text("❌ Invalid form format.")
        return

    buyer, seller, amount = match.groups()
    deal_id = db.add_deal(buyer, seller, amount, admin_id, status="IN_PROGRESS")
    timestamp = datetime.utcnow().strftime(cfg.TIME_FORMAT)

    await update.message.reply_text(
        f"✅ ESCROW STARTED\n"
        f"✅👤 BUYER: {buyer}\n"
        f"SELLER: {seller}\n"
        f"AMOUNT: ${amount}\n"
        f"STARTED BY: {user.mention_html()}\n"
        f"ID: {deal_id}-{timestamp}",
        parse_mode="HTML"
    )

# ---------------------------
# /close command: finish a deal
# ---------------------------
async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_id = user.id

    # Check if replied to a message
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    elif context.args:
        deal_id = context.args[0]
        text = db.get_form_by_id(deal_id)
        if not text:
            await update.message.reply_text("❌ No deal found with that ID.")
            return
    else:
        await update.message.reply_text("❌ Reply to a deal message or provide deal ID.")
        return

    deal = db.get_deal_by_text(text)
    if not deal:
        await update.message.reply_text("❌ Could not find a deal associated with this form/message.")
        return

    db.update_deal_status(deal['id'], "COMPLETED", released_by=admin_id)
    timestamp = datetime.utcnow().strftime(cfg.TIME_FORMAT)

    await update.message.reply_text(
        f"✅ ESCROW DONE\n"
        f"✅👤 BUYER: {deal['buyer']} 🔗\n"
        f"SELLER: {deal['seller']} 💰\n"
        f"RELEASED AMOUNT: ${deal['amount']}\n"
        f"🛡️ RELEASED BY: {user.mention_html()}\n"
        f"ID: {deal['id']}-{timestamp}",
        parse_mode="HTML"
            )
