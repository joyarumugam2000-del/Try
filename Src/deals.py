import re
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from .utils import gen_deal_code, now_ts, is_admin
from .db import add_deal, set_deal_message, mark_deal_closed, add_invite_link, get_setting, set_setting

# DVA/Escrow PM link
async def _send_dva_link(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    chat_id = int(get_setting("DVA_GROUP_ID") or 0)
    if not chat_id: return None
    link = await context.bot.create_chat_invite_link(chat_id=chat_id, member_limit=1)
    add_invite_link(link.invite_link, chat_id, user_id, now_ts())
    try:
        await context.bot.send_message(user_id, f"One-time DVA link:\n{link.invite_link}")
    except: pass
    return link.invite_link

async def trigger_dva_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = await _send_dva_link(context, update.effective_user.id)
    if link: await update.effective_message.reply_text("Check PM for DVA link")
    else: await update.effective_message.reply_text("DVA group not set. Owner run /dvaonly")

async def cmd_dvaonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(context.bot_data.get("OWNER_ID")): return
    set_setting("DVA_GROUP_ID", str(update.effective_chat.id))
    await update.effective_message.reply_text(f"DVA group set (chat_id={update.effective_chat.id})")

# Admin add deal
async def admin_keyword_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message or msg.text.lower().strip() != "add": return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    admin_name = update.effective_user.username or update.effective_user.first_name
    if not await is_admin(context, chat_id, user_id):
        await msg.reply_text("Must be admin to add deal"); return

    lines = msg.reply_to_message.text.splitlines()
    data = {}
    for line in lines:
        if ":" in line: key,val=line.split(":",1); data[key.strip().lower()]=val.strip()

    buyer = data.get("buyer"); seller = data.get("seller")
    try: amount=float(data.get("amount",0))
    except: amount=0
    payment_mode=data.get("payment mode",""); description=data.get("description","")
    if not buyer or not seller or amount<=0: await msg.reply_text("Invalid form"); return

    code=gen_deal_code(); fee=round(amount*0.01,2)
    add_deal(code,buyer,seller,amount,fee,admin_name,now_ts(),chat_id,msg.reply_to_message.message_id)
    deal_msg = await context.bot.send_message(
        chat_id,
        f"🧾 Deal `{code}`\nBuyer:{buyer}\nSeller:{seller}\nAmount:{amount}\nFee:{fee}\nPayment:{payment_mode}\nDesc:{description}\nAdded by:@{admin_name}\nReply 'close' to finish."
    )
    set_deal_message(code,deal_msg.chat_id,deal_msg.message_id)
    await msg.reply_text(f"✅ Deal `{code}` added.", parse_mode="Markdown")

# Admin close deal
async def admin_keyword_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message or msg.text.lower().strip() != "close": return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    admin_name = update.effective_user.username or update.effective_user.first_name
    if not await is_admin(context, chat_id, user_id):
        await msg.reply_text("Must be admin to close deal"); return
    m = re.search(r'`(DL-[A-Z0-9]{8})`', msg.reply_to_message.text)
    if not m: await msg.reply_text("Cannot find deal code"); return
    code=m.group(1)
    mark_deal_closed(code,admin_name)
    await msg.reply_to_message.reply_text(f"✅ Deal `{code}` closed by @{admin_name}.", parse_mode="Markdown")

def build_handlers():
    return [
        CommandHandler("dvaonly", cmd_dvaonly),
        MessageHandler(filters.Regex(r"(?i)\b(dva|escrow)\b"), trigger_dva_link),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_add),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_keyword_close)
    ]
