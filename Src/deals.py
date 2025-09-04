# deals.py
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CommandHandler, CallbackQueryHandler, filters
)
from .db import add_deal, set_deal_message, mark_deal_closed, add_invite_link, get_setting
from .utils import gen_deal_code, now_ts, is_admin, is_owner
from .config import ESCROW_FEE_RATE, KICK_AFTER_SECONDS

# --- Conversation states ---
ASK_BUYER, ASK_SELLER, ASK_AMOUNT, CONFIRM = range(4)
pending_forms: Dict[int, Dict[str, Any]] = {}

# --- DVA/Escrow ---
async def _send_dva_link(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    chat_id = int(get_setting("DVA_GROUP_ID") or 0)
    if not chat_id:
        return None
    link = await context.bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    add_invite_link(link.invite_link, chat_id, user_id, now_ts())
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Here is your one-time invite link:\n{link.invite_link}\n⚠️ Will expire after join."
        )
    except Exception:
        pass
    return link.invite_link

async def trigger_dva_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    link = await _send_dva_link(context, user.id)
    if link:
        await update.effective_message.reply_text("I sent you a one-time DVA/Escrow link in DM.")
    else:
        await update.effective_message.reply_text("DVA/Escrow group not set. Owner must run /dvaonly.")

async def cmd_dvaonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not await is_owner(context, user.id):
        return
    from .db import set_setting
    set_setting("DVA_GROUP_ID", str(chat.id))
    await update.effective_message.reply_text(f"This chat is now the DVA/Escrow room (chat_id={chat.id}).")

# --- Deal Form ---
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_forms[user_id] = {"buyer": None, "seller": None, "amount": None}
    await update.effective_message.reply_text("Buyer username? (e.g., @buyer)")
    return ASK_BUYER

async def ask_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_forms[user_id]["buyer"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("Seller username? (e.g., @seller)")
    return ASK_SELLER

async def ask_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_forms[user_id]["seller"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("Deal amount? (numbers only, e.g., 2500)")
    return ASK_AMOUNT

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amt = float(update.effective_message.text.strip())
    except Exception:
        await update.effective_message.reply_text("Please send a valid number amount.")
        return ASK_AMOUNT

    pending_forms[user_id]["amount"] = amt
    code = gen_deal_code()
    pending_forms[user_id]["code"] = code
    fee = round(amt * ESCROW_FEE_RATE, 2)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Submit to DVA group", callback_data=f"deal_submit:{code}")],
        [InlineKeyboardButton("Cancel", callback_data=f"deal_cancel:{code}")]
    ])

    b = pending_forms[user_id]["buyer"]
    s = pending_forms[user_id]["seller"]
    await update.effective_message.reply_text(
        f"Deal draft `{code}`\nBuyer: {b}\nSeller: {s}\nAmount: {amt}\nEscrow fee (1%): {fee}\nSubmit to DVA group?",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return CONFIRM

async def cancel_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_forms.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("Cancelled.")
    return ConversationHandler.END

# --- CallbackQuery for submit/cancel ---
async def cb_deal_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user_id = q.from_user.id

    if data.startswith("deal_cancel:"):
        code = data.split(":")[1]
        pending_forms.pop(user_id, None)
        await q.edit_message_text(f"Deal draft `{code}` cancelled.", parse_mode="Markdown")
        return

    if data.startswith("deal_submit:"):
        code = data.split(":")[1]
        form = pending_forms.get(user_id)
        if not form:
            await q.edit_message_text("Session expired. Please /form again.")
            return

        chat_id = int(get_setting("DVA_GROUP_ID") or 0)
        if not chat_id:
            await q.edit_message_text("DVA/Escrow group not set. Owner must run /dvaonly.")
            return

        amount = float(form["amount"])
        fee = round(amount * ESCROW_FEE_RATE, 2)
        did = add_deal(code, form["buyer"], form["seller"], amount, fee, user_id, now_ts())

        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🧾 Deal `{code}`\nBuyer: {form['buyer']}\nSeller: {form['seller']}\n"
                f"Amount: {amount}\nFee: {fee}\nAdded by: @{q.from_user.username or 'admin'}\n\n"
                "Reply `add` to open this deal."
            ),
            parse_mode="Markdown"
        )

        set_deal_message(code, msg.chat_id, msg.message_id)
        pending_forms.pop(user_id, None)

# --- Admin Add/Close ---
async def admin_keyword_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "add" or not msg.reply_to_message:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not await is_admin(context, chat_id, user_id):
        return

    import re
    m = re.search(r'`(DL-[A-Z0-9]{8})`', msg.reply_to_message.text or "")
    if not m:
        return
    code = m.group(1)
    # Save who added
    from .db import add_deal  # already saved in db when submitted
    await msg.reply_to_message.reply_text(f"✅ Deal `{code}` opened. Admin @{msg.from_user.username} added.")

async def admin_keyword_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "close" or not msg.reply_to_message:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not await is_admin(context, chat_id, user_id):
        return

    import re
    m = re.search(r'`(DL-[A-Z0-9]{8})`', msg.reply_to_message.text or "")
    if not m:
        await msg.reply_text("Could not find deal code in the replied message.")
        return
    code = m.group(1)

    mark_deal_closed(code)
    await msg.reply_to_message.reply_text(
        f"✅ Deal `{code}` closed.\nClosed by: @{msg.from_user.username}",
        parse_mode="Markdown"
    )

# --- Stay callback & kick ---
async def cb_stay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Kick canceled for you (if scheduled).")
    await q.edit_message_text(q.message.text + "\n\n✅ Stay confirmed.")

async def kick_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data or {}
    chat_id = data.get("chat_id")
    try:
        await context.bot.send_message(chat_id, "⏰ Kick window elapsed for closed deal.")
    except Exception:
        pass

# --- Build handlers ---
def build_handlers():
    return [
        CommandHandler("dvaonly", cmd_dvaonly),
        CommandHandler("form", start_form),
        ConversationHandler(
            entry_points=[CommandHandler("form", start_form)],
            states={
                ASK_BUYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buyer)],
                ASK_SELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_seller)],
                ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
                CONFIRM: [CallbackQueryHandler(cb_deal_actions, pattern=r"^deal_(submit|cancel):")]
            },
            fallbacks=[CommandHandler("cancel", cancel_form)],
            name="DEAL_FORM",
            persistent=False
        ),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_add),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_close),
        CallbackQueryHandler(cb_stay, pattern=r"^stay:"),
        MessageHandler(filters.Regex(r"(?i)\b(dva|escrow)\b"), trigger_dva_link)
]
