from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from .config import ESCROW_FEE_RATE, KICK_AFTER_SECONDS
from .db import add_deal, set_deal_message, mark_deal_closed, add_invite_link, get_setting, set_setting
from .utils import gen_deal_code, now_ts, is_admin, is_owner

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
            text=f"Here is your one-time invite link to the DVA/Escrow room:\n{link.invite_link}\n⚠️ This link will be revoked after you join."
        )
    except Exception:
        pass
    return link.invite_link

async def trigger_dva_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    link = await _send_dva_link(context, user.id)
    if link:
        await update.effective_message.reply_text("I sent you a one-time invite link in DM. Check your PMs.")
    else:
        await update.effective_message.reply_text("DVA/Escrow group is not set. Owner must run /dvaonly in target group.")

async def cmd_dvaonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not await is_owner(context, user.id):
        return
    set_setting("DVA_GROUP_ID", str(chat.id))
    await update.effective_message.reply_text(f"This chat is now set as the DVA/Escrow room (chat_id={chat.id}).")

# --- Direct deal message in group ---
async def parse_deal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    text = msg.text or ""
    lines = [line.strip() for line in text.splitlines()]
    if len(lines) < 3:
        return

    # Parse fields
    data = {}
    for line in lines:
        if line.lower().startswith("buyer:"):
            data["buyer"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("seller:"):
            data["seller"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("amount:"):
            try:
                data["amount"] = float(line.split(":", 1)[1].strip())
            except Exception:
                await msg.reply_text("Invalid amount. Use numbers only.")
                return
        elif line.lower().startswith("description:"):
            data["description"] = line.split(":", 1)[1].strip()

    if not all(k in data for k in ("buyer", "seller", "amount", "description")):
        return

    code = gen_deal_code()
    fee = round(data["amount"] * ESCROW_FEE_RATE, 2)

    # Save deal
    did = add_deal(code, data["buyer"], data["seller"], data["amount"], fee, msg.from_user.id, now_ts())
    await msg.reply_text(
        f"🧾 Deal `{code}`\nBuyer: {data['buyer']}\nSeller: {data['seller']}\nAmount: {data['amount']}\n"
        f"Fee: {fee}\nDescription: {data['description']}\n\nAdmin, reply `add` to start the deal.",
        parse_mode="Markdown"
    )
    set_deal_message(code, msg.chat.id, msg.message_id)

# --- Admin add / close ---
async def admin_keyword_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "add" or not msg.reply_to_message:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not await is_admin(context, chat_id, user_id):
        return

    text = msg.reply_to_message.text
    import re
    m = re.search(r'`(DL-[A-Z0-9]{8})`', text)
    if not m:
        await msg.reply_text("Couldn't find deal code in replied message.")
        return
    code = m.group(1)

    # Update deal with admin who added
    await msg.reply_to_message.reply_text(f"✅ Deal `{code}` opened by admin {msg.from_user.mention_markdown()}", parse_mode="Markdown")

async def admin_keyword_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.text.strip().lower() != "close" or not msg.reply_to_message:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not await is_admin(context, chat_id, user_id):
        return

    text = msg.reply_to_message.text
    import re
    m = re.search(r'`(DL-[A-Z0-9]{8})`', text)
    if not m:
        await msg.reply_text("Couldn't find deal code in replied message.")
        return
    code = m.group(1)

    mark_deal_closed(code)
    await msg.reply_to_message.reply_text(
        f"✅ Deal `{code}` closed by admin {msg.from_user.mention_markdown()}.\nUsers joined via one-time links will be kicked in 5 minutes.",
        parse_mode="Markdown"
    )
    # Schedule kick job
    context.job_queue.run_once(kick_job, when=KICK_AFTER_SECONDS, data={"code": code, "chat_id": chat_id})

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
        MessageHandler(filters.TEXT & ~filters.COMMAND, parse_deal_message),
        MessageHandler(filters.Regex(r"(?i)^add$") & filters.REPLY, admin_keyword_add),
        MessageHandler(filters.Regex(r"(?i)^close$") & filters.REPLY, admin_keyword_close),
        CallbackQueryHandler(cb_stay, pattern=r"^stay:"),
        MessageHandler(filters.Regex(r"(?i)\b(dva|escrow)\b"), trigger_dva_link)
    ]
