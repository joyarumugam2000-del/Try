import re
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from .utils import gen_deal_code, now_ts, is_admin
from .db import add_deal, set_deal_message, mark_deal_closed, get_setting, set_setting, add_invite_link

# --- DVA / Escrow one-time link ---
async def _send_dva_link(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    chat_id = int(get_setting("DVA_GROUP_ID") or 0)
    if not chat_id:
        return None
    link = await context.bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    add_invite_link(link.invite_link, chat_id, user_id, now_ts())
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Here is your one-time invite link to the DVA/Escrow room:\n{link.invite_link}\n⚠️ Link revoked after join."
        )
    except Exception:
        pass
    return link.invite_link

async def trigger_dva_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    link = await _send_dva_link(context, user.id)
    if link:
        await update.effective_message.reply_text("✅ Check your PM for the one-time DVA/Escrow link.")
    else:
        await update.effective_message.reply_text("DVA/Escrow group not set. Owner must run /dvaonly.")

async def cmd_dvaonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if str(user.id) != str(context.bot_data.get("OWNER_ID")):
        return
    set_setting("DVA_GROUP_ID", str(chat.id))
    await update.effective_message.reply_text(f"This chat is now set as the DVA/Escrow room (chat_id={chat.id}).")

# --- Admin adds deal by replying 'add' ---
async def admin_keyword_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "add" or not msg.reply_to_message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    admin_name = update.effective_user.username or update.effective_user.first_name

    if not await is_admin(context, chat_id, user_id):
        return

    lines = msg.reply_to_message.text.splitlines()
    data = {}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip().lower()] = val.strip()

    buyer = data.get("buyer")
    seller = data.get("seller")
    amount = float(data.get("amount", 0))
    payment_mode = data.get("payment mode", "")
    description = data.get("description", "")

    if not buyer or not seller or not amount:
        await msg.reply_text("Form missing required fields.")
        return

    code = gen_deal_code()
    fee = round(amount * 0.01, 2)  # 1% fee

    did = add_deal(code, buyer, seller, amount, fee, user_id, now_ts(), admin_add=admin_name)

    deal_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🧾 Deal `{code}`\n"
            f"Buyer: {buyer}\n"
            f"Seller: {seller}\n"
            f"Amount: {amount}\n"
            f"Fee: {fee}\n"
            f"Payment mode: {payment_mode}\n"
            f"Description: {description}\n"
            f"Added by Admin: @{admin_name}\n\n"
            "Reply 'close' to finish this deal."
        )
    )
    set_deal_message(code, deal_msg.chat_id, deal_msg.message_id)
    await msg.reply_text(f"✅ Deal `{code}` added successfully.", parse_mode="Markdown")

# --- Admin closes deal by replying 'close' ---
async def admin_keyword_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "close" or not msg.reply_to_message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    admin_name = update.effective_user.username or update.effective_user.first_name

    if not await is_admin(context, chat_id, user_id):
        return

    m = re.search(r'`(DL-[A-Z0-9]{8})`', msg.reply_to_message.text or "")
    if not m:
        await msg.reply_text("Cannot find deal code in the replied message.")
        return

    code = m.group(1)
    mark_deal_closed(code, admin_close=admin_name)

    await msg.reply_to_message.reply_text(
        f"✅ Deal `{code}` closed by Admin @{admin_name}.",
        parse_mode="Markdown"
    )

# --- Build handlers for main.py ---
def build_handlers():
    return [
        CommandHandler("dvaonly", cmd_dvaonly),
        MessageHandler(filters.Regex(r"(?i)\b(dva|escrow)\b"), trigger_dva_link),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_add),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_close),
        ]
