from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, ConversationHandler, filters
from .db import add_deal, mark_deal_closed, set_deal_message, add_invite_link, get_setting, set_setting
from .utils import gen_deal_code, now_ts, is_admin, is_owner

# --- States ---
ASK_FORM = range(1)
pending_forms: Dict[int, Dict[str, Any]] = {}

# --- DVA / Escrow link ---
async def _send_dva_link(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    chat_id = int(get_setting("DVA_GROUP_ID") or 0)
    if not chat_id:
        return None
    link = await context.bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    add_invite_link(link.invite_link, chat_id, user_id, now_ts())
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Here is your one-time DVA/Escrow link:\n{link.invite_link}"
        )
    except Exception:
        pass
    return link.invite_link

# --- Form trigger ---
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Please fill your deal like this in the group:\n\n"
        "Seller: @seller\n"
        "Buyer: @buyer\n"
        "Amount: 2500\n"
        "Payment mode: UPI / Bank / Cash\n"
        "Description: Payment for X\n\n"
        "Admin will reply `add` to start your deal."
    )
    return ASK_FORM

# --- Admin add deal ---
async def admin_add_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "add" or not msg.reply_to_message:
        return
    admin_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not await is_admin(context, chat_id, admin_id):
        return

    # Parse deal info
    text = msg.reply_to_message.text
    lines = text.splitlines()
    try:
        seller = lines[0].split(":", 1)[1].strip()
        buyer = lines[1].split(":", 1)[1].strip()
        amount = float(lines[2].split(":", 1)[1].strip())
        payment_mode = lines[3].split(":", 1)[1].strip()
        description = lines[4].split(":", 1)[1].strip()
    except Exception:
        await msg.reply_text("❌ Invalid form format. Make sure all fields are present.")
        return

    fee = round(amount * 0.01, 2)  # 1% fee
    code = gen_deal_code()
    deal_id = add_deal(code, buyer, seller, amount, fee, admin_id, now_ts())

    await msg.reply_text(
        f"🧾 Deal `{code}` added by admin @{update.effective_user.username}\n"
        f"Buyer: {buyer}\nSeller: {seller}\nAmount: {amount}\nPayment mode: {payment_mode}\n"
        f"Fee (1%): {fee}\nDescription: {description}\n\n"
        "Reply `close` to close this deal when finished."
    )

# --- Admin close deal ---
async def admin_close_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "close" or not msg.reply_to_message:
        return
    admin_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not await is_admin(context, chat_id, admin_id):
        return

    import re
    m = re.search(r'`(DL-[A-Z0-9]{8})`', msg.reply_to_message.text or "")
    if not m:
        await msg.reply_text("❌ Couldn't find deal code in the replied message.")
        return
    code = m.group(1)
    mark_deal_closed(code)

    await msg.reply_to_message.reply_text(
        f"✅ Deal `{code}` closed by admin @{update.effective_user.username}."
    )

# --- Build handlers ---
def build_handlers():
    return [
        CommandHandler("form", start_form),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_deal),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_close_deal),
    ]
