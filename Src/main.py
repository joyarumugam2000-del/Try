"""
main.py - Telegram Escrow/DVA Group Bot
Requires python-telegram-bot v20+
"""

import logging
import traceback

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config as cfg
from db import DB
import utils
import deals

# conversation states
(T_FORM_TYPE, T_BUYER, T_SELLER, T_AMOUNT, T_PURPOSE, T_CONFIRM) = range(6)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

db = DB(cfg.DB_PATH)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Use /form in a group to create an ESCROW or DVA form. (Bot works in groups only.)"
    )


# ---------- FORM CONVERSATION ----------
async def form_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("/form works in groups only. Add me to a group and try again.")
        return ConversationHandler.END

    await update.message.reply_text("Starting form. Reply with the type: ESCROW or DVA")
    return T_FORM_TYPE


async def form_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text not in ("ESCROW", "DVA"):
        await update.message.reply_text("Please send either ESCROW or DVA.")
        return T_FORM_TYPE
    context.user_data["form_type"] = text
    await update.message.reply_text("Send BUYER username (start with @). Example: @buyerusername")
    return T_BUYER


async def form_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buyer = update.message.text.strip()
    if not buyer.startswith("@"):
        await update.message.reply_text("Buyer username must start with @. Try again.")
        return T_BUYER
    context.user_data["buyer"] = buyer
    await update.message.reply_text("Send SELLER username (start with @). Example: @sellerusername")
    return T_SELLER


async def form_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = update.message.text.strip()
    if not seller.startswith("@"):
        await update.message.reply_text("Seller username must start with @. Try again.")
        return T_SELLER
    context.user_data["seller"] = seller
    await update.message.reply_text("Send AMOUNT (integer or decimal). Example: 99 or 99.50")
    return T_AMOUNT


async def form_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip().replace(",", "")
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("Invalid amount. Send a positive number. Example: 99 or 99.50")
        return T_AMOUNT
    context.user_data["amount"] = amount
    await update.message.reply_text("Send Purpose / short description of the deal.")
    return T_PURPOSE


async def form_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    purpose = update.message.text.strip()
    context.user_data["purpose"] = purpose

    preview = deals.format_form_preview(
        form_type=context.user_data["form_type"],
        buyer=context.user_data["buyer"],
        seller=context.user_data["seller"],
        amount=context.user_data["amount"],
        purpose=context.user_data["purpose"],
        posted_by=getattr(update.effective_user, "username", str(update.effective_user.id)),
        created_at=utils.now_iso(),
    )

    await update.message.reply_text(preview + "\n\nReply YES to save and post the form, or NO to cancel.")
    return T_CONFIRM


async def form_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in ("yes", "y"):
        await update.message.reply_text("Form cancelled.")
        return ConversationHandler.END

    chat = update.effective_chat
    user = update.effective_user

    created_at = utils.now_iso()
    # Create form record
    form_id = db.create_form(
        chat_id=chat.id,
        message_id=0,
        form_type=context.user_data["form_type"],
        buyer=context.user_data["buyer"],
        seller=context.user_data["seller"],
        amount=context.user_data["amount"],
        purpose=context.user_data["purpose"],
        filler_id=user.id,
        filler_username=getattr(user, "username", str(user.id)),
        created_at=created_at,
    )

    # Post visible form message
    post_text = deals.format_form_post(
        form_id=form_id,
        form_type=context.user_data["form_type"],
        buyer=context.user_data["buyer"],
        seller=context.user_data["seller"],
        amount=context.user_data["amount"],
        purpose=context.user_data["purpose"],
        filler_username=getattr(user, "username", str(user.id)),
        created_at=created_at,
    )

    posted = await update.message.reply_text(post_text)
    db.update_form_message_id(form_id, posted.message_id)

    # Log
    try:
        if cfg.LOG_CHANNEL_ID:
            await context.bot.send_message(cfg.LOG_CHANNEL_ID, f"[FORM CREATED]\n{post_text}")
    except Exception as e:
        logger.warning("Failed to post to log channel: %s", e)

    await update.message.reply_text(f"Form saved with ID {form_id}. An admin can /add {form_id} to accept the deal.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Form cancelled.")
    return ConversationHandler.END


# ---------- ADMIN COMMANDS ----------
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("/add can be used in groups only.")
        return

    is_admin = await utils.is_user_admin(context.bot, chat.id, user.id)
    if not is_admin:
        await update.message.reply_text("Only group admins can accept deals (use /add <form_id>).")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /add <form_id>")
        return

    try:
        form_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Form id must be a number. Usage: /add <form_id>")
        return

    form = db.get_form(form_id)
    if not form:
        await update.message.reply_text(f"Form id {form_id} not found.")
        return

    if form["status"] != "pending":
        await update.message.reply_text(f"Form {form_id} is not pending (status: {form['status']}).")
        return

    # Create deal
    created_at = utils.now_iso()
    deal_id = db.add_deal(form_id=form_id, admin_id=user.id, admin_username=getattr(user, "username", str(user.id)), created_at=created_at)

    db.update_form_accept(form_id=form_id, admin_id=user.id, admin_username=getattr(user, "username", str(user.id)), accepted_at=created_at, deal_id=deal_id)

    add_text = deals.format_deal_added(
        form_id=form_id,
        buyer=form["buyer"],
        seller=form["seller"],
        amount=form["amount"],
        admin_username=getattr(user, "username", str(user.id)),
        deal_id=deal_id,
        accepted_at=created_at,
    )

    await update.message.reply_text(add_text)

    try:
        if cfg.LOG_CHANNEL_ID:
            await context.bot.send_message(cfg.LOG_CHANNEL_ID, f"[DEAL ADDED]\n{add_text}")
    except Exception as e:
        logger.warning("Failed to post to log channel: %s", e)


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("/close works in groups only. Reply to the form message with /close.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("To close a deal, reply to the original form message with /close.")
        return

    replied_msg = update.message.reply_to_message
    form = db.get_form_by_message(chat.id, replied_msg.message_id)
    if not form:
        await update.message.reply_text("Could not find a form associated with the replied message.")
        return

    deal = db.get_deal_by_form(form_id=form["id"]) if form else None
    if not deal:
        await update.message.reply_text("No active deal found for this form. Maybe it was never accepted.")
        return

    if deal["admin_id"] != user.id:
        await update.message.reply_text("Only the admin who accepted/added this deal can close it.")
        return

    closed_at = utils.now_iso()
    db.close_deal(deal_id=deal["id"], closed_at=closed_at)
    db.update_form_closed(form_id=form["id"], closed_at=closed_at)

    closed_text = deals.format_deal_closed(
        form_id=form["id"],
        buyer=form["buyer"],
        seller=form["seller"],
        amount=form["amount"],
        admin_username=deal["admin_username"],
        deal_id=deal["id"],
        closed_at=closed_at,
    )

    await update.message.reply_text(closed_text)

    try:
        if cfg.LOG_CHANNEL_ID:
            await context.bot.send_message(cfg.LOG_CHANNEL_ID, f"[DEAL CLOSED]\n{closed_text}")
    except Exception as e:
        logger.warning("Failed to post to log channel: %s", e)


async def list_forms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command works in groups only.")
        return

    is_admin = await utils.is_user_admin(context.bot, chat.id, user.id)
    if not is_admin:
        await update.message.reply_text("Only group admins can list forms.")
        return

    rows = db.list_forms(chat.id)
    if not rows:
        await update.message.reply_text("No pending forms.")
        return

    text = "Pending forms:\n"
    for r in rows:
        text += f"ID {r['id']}: {r['form_type']} buyer:{r['buyer']} seller:{r['seller']} amount:{r['amount']} created:{r['created_at']}\n"
    await update.message.reply_text(text)


async def list_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command works in groups only.")
        return

    is_admin = await utils.is_user_admin(context.bot, chat.id, user.id)
    if not is_admin:
        await update.message.reply_text("Only group admins can list deals.")
        return

    rows = db.list_deals(chat.id)
    if not rows:
        await update.message.reply_text("No deals found.")
        return

    text = "Deals:\n"
    for r in rows:
        text += f"Deal {r['id']} (Form {r['form_id']}): status:{r['status']} admin:{r['admin_username']} created:{r['created_at']} closed:{r['closed_at']}\n"
    await update.message.reply_text(text)


def main():
    token = cfg.BOT_TOKEN
    if not token or token == "PUT-YOUR-TOKEN-HERE":
        raise RuntimeError("Set BOT_TOKEN in config.py or environment variable BOT_TOKEN")

    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("form", form_start)],
        states={
            T_FORM_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_type)],
            T_BUYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_buyer)],
            T_SELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_seller)],
            T_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_amount)],
            T_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_purpose)],
            T_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, form_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("close", close_command))
    app.add_handler(CommandHandler("list_forms", list_forms))
    app.add_handler(CommandHandler("list_deals", list_deals))

    logger.info("Starting bot...")
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
