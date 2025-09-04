from typing import Dict, Any, Optional
import re
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, 
    CommandHandler, CallbackQueryHandler, filters
)

from .config import ESCROW_FEE_RATE, KICK_AFTER_SECONDS, LOG_CHANNEL_ID
from .db import add_deal, set_deal_message, mark_deal_closed, add_invite_link, get_setting, set_setting
from .utils import gen_deal_code, now_ts, is_admin, is_owner

ASK_BUYER, ASK_SELLER, ASK_AMOUNT, ASK_DESC, CONFIRM = range(5)
pending_forms: Dict[int, Dict[str, Any]] = {}

# --- Utility: log all actions ---
async def log_action(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"Log failed: {e}")

# --- Send one-time DVA link ---
async def _send_dva_link(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    chat_id = int(get_setting("DVA_GROUP_ID") or 0)
    if not chat_id:
        return None
    link = await context.bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    add_invite_link(link.invite_link, chat_id, user_id, now_ts())
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Here is your one-time invite link:\n{link.invite_link}\n⚠️ It will be revoked after you join."
        )
    except Exception:
        pass
    return link.invite_link

async def trigger_dva_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    link = await _send_dva_link(context, user.id)
    if link:
        await update.effective_message.reply_text("✅ Check your DM for a one-time invite link.")
        await log_action(context, f"🔗 DVA link sent to {user.mention_html()}")
    else:
        await update.effective_message.reply_text("❌ DVA/Escrow group not configured. Ask owner to run /dvaonly.")

async def cmd_dvaonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not await is_owner(context, user.id):
        return
    set_setting("DVA_GROUP_ID", str(chat.id))
    await update.effective_message.reply_text(f"✅ This chat is now set as DVA/Escrow room ({chat.id})")
    await log_action(context, f"⚙️ Group {chat.title} set as DVA room by {user.mention_html()}")

# --- Deal form conversation ---
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_forms[user_id] = {"buyer": None, "seller": None, "amount": None, "desc": None}
    await update.effective_message.reply_text("👤 Buyer username? (e.g., @buyer)")
    return ASK_BUYER

async def ask_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    buyer = update.effective_message.text.strip()
    if not re.match(r"^@\w+$", buyer):
        await update.effective_message.reply_text("⚠️ Invalid username. Must start with @")
        return ASK_BUYER
    pending_forms[user_id]["buyer"] = buyer
    await update.effective_message.reply_text("👤 Seller username? (e.g., @seller)")
    return ASK_SELLER

async def ask_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    seller = update.effective_message.text.strip()
    if not re.match(r"^@\w+$", seller):
        await update.effective_message.reply_text("⚠️ Invalid username. Must start with @")
        return ASK_SELLER
    pending_forms[user_id]["seller"] = seller
    await update.effective_message.reply_text("💰 Deal amount? (numbers only, e.g., 2500)")
    return ASK_AMOUNT

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amt = float(update.effective_message.text.strip())
    except Exception:
        await update.effective_message.reply_text("⚠️ Please send a valid number.")
        return ASK_AMOUNT
    pending_forms[user_id]["amount"] = amt
    await update.effective_message.reply_text("📝 Deal description?")
    return ASK_DESC

async def ask_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    desc = update.effective_message.text.strip()
    if not desc:
        await update.effective_message.reply_text("⚠️ Description cannot be empty.")
        return ASK_DESC
    pending_forms[user_id]["desc"] = desc
    amt = pending_forms[user_id]["amount"]
    fee = round(amt * ESCROW_FEE_RATE, 2)
    code = gen_deal_code()
    pending_forms[user_id]["code"] = code
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Submit to DVA group", callback_data=f"deal_submit:{code}")],
        [InlineKeyboardButton("Cancel", callback_data=f"deal_cancel:{code}")]
    ])
    await update.effective_message.reply_text(
        f"📑 Deal draft `{code}`\n"
        f"Buyer: {pending_forms[user_id]['buyer']}\n"
        f"Seller: {pending_forms[user_id]['seller']}\n"
        f"Amount: {amt}\n"
        f"Fee (1%): {fee}\n"
        f"Description: {desc}\n\n"
        "Submit to DVA group?",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return CONFIRM

async def cancel_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_forms.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# --- Callback deal submit/cancel ---
async def cb_deal_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data.startswith("deal_cancel:"):
        code = data.split(":")[1]
        pending_forms.pop(q.from_user.id, None)
        await q.edit_message_text(f"❌ Deal draft `{code}` cancelled.", parse_mode="Markdown")
        return

    if data.startswith("deal_submit:"):
        code = data.split(":")[1]
        form = pending_forms.get(q.from_user.id)
        if not form:
            await q.edit_message_text("Session expired. Please /form again.")
            return
        chat_id = int(get_setting("DVA_GROUP_ID") or 0)
        if not chat_id:
            await q.edit_message_text("❌ DVA group not set. Ask owner to run /dvaonly.")
            return
        amount = float(form["amount"])
        fee = round(amount * ESCROW_FEE_RATE, 2)
        add_deal(code, form["buyer"], form["seller"], amount, fee, q.from_user.id, now_ts())
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🧾 New deal `{code}`\n"
                f"Buyer: {form['buyer']}\n"
                f"Seller: {form['seller']}\n"
                f"Amount: {amount}\n"
                f"Fee (1%): {fee}\n"
                f"Description: {form['desc']}\n\n"
                "Reply `add` to approve."
            ),
            parse_mode="Markdown"
        )
        set_deal_message(code, msg.chat_id, msg.message_id)
        await q.edit_message_text(f"✅ Deal `{code}` submitted.", parse_mode="Markdown")
        await log_action(context, f"📌 New Deal `{code}`\nBuyer: {form['buyer']}\nSeller: {form['seller']}\nAmount: {amount}\nDesc: {form['desc']}")
        pending_forms.pop(q.from_user.id, None)

# --- Admin add ---
async def admin_keyword_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "add" or not msg.reply_to_message:
        return
    if not await is_admin(context, msg.chat_id, update.effective_user.id):
        return
    await msg.reply_to_message.reply_text("✅ Deal opened. Reply `close` to finish.")
    await log_action(context, f"✅ Deal Approved by {update.effective_user.mention_html()}")

# --- Admin close ---
async def admin_keyword_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "close" or not msg.reply_to_message:
        return
    if not await is_admin(context, msg.chat_id, update.effective_user.id):
        return
    m = re.search(r'`(DL-[A-Z0-9]{8})`', msg.reply_to_message.text or "")
    if not m:
        await msg.reply_text("⚠️ Couldn’t find deal code.")
        return
    code = m.group(1)
    mark_deal_closed(code)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Stay", callback_data=f"stay:{code}")]])
    await msg.reply_to_message.reply_text(
        f"❌ Deal `{code}` closed.\nUsers will be kicked in {KICK_AFTER_SECONDS//60} min unless they press Stay.",
        reply_markup=kb
    )
    await log_action(context, f"❌ Deal `{code}` closed by {update.effective_user.mention_html()}")
    context.job_queue.run_once(kick_job, when=KICK_AFTER_SECONDS, data={"code": code, "chat_id": msg.chat_id})

async def cb_stay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Stay confirmed.")
    await q.edit_message_text(q.message.text + "\n✅ Stay confirmed.")
    await log_action(context, f"🛑 Stay confirmed for deal.")

async def kick_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data or {}
    chat_id = data.get("chat_id")
    code = data.get("code")
    try:
        await context.bot.send_message(chat_id, f"⏰ Kick window elapsed for deal `{code}`.")
        await log_action(context, f"🚨 Kick executed for deal `{code}`")
    except Exception:
        pass

# --- Handlers ---
def build_handlers():
    return [
        CommandHandler("dvaonly", cmd_dvaonly),
        CommandHandler("form", start_form),
        MessageHandler(filters.Regex(r"(?i)\b(dva|escrow)\b"), trigger_dva_link),
        ConversationHandler(
            entry_points=[CommandHandler("form", start_form)],
            states={
                ASK_BUYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buyer)],
                ASK_SELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_seller)],
                ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
                ASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_desc)],
                CONFIRM: [CallbackQueryHandler(cb_deal_actions, pattern=r"^deal_(submit|cancel):")]
            },
            fallbacks=[CommandHandler("cancel", cancel_form)],
        ),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_add),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_close),
        CallbackQueryHandler(cb_stay, pattern=r"^stay:")
        ]
