from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update
from config import BOT_TOKEN, ADMIN_IDS
from deals import post_deal, start_deal, cancel_deal
from seller import join_deal_seller
from buyer import join_deal_buyer

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send your deal form:\nSeller: @username\nBuyer: @username\nAmount: 100\nMore details: optional")

async def submit_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.message.text.split('\n')
        if len(msg) < 3:
            await update.message.reply_text("Form invalid! Must include Seller, Buyer, Amount.")
            return
        seller = msg[0].split(':')[1].strip().replace('@','')
        buyer = msg[1].split(':')[1].strip().replace('@','')
        amount = int(msg[2].split(':')[1].strip())
        details = msg[3].split(':')[1].strip() if len(msg) > 3 else ""
        deal_id = await post_deal(context.bot, seller, buyer, amount, details)
        await update.message.reply_text(f"Deal submitted! Pending in DVA group with ID: {deal_id}")
    except Exception as e:
        await update.message.reply_text(f"Error processing form: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    action = data[0]
    deal_id = data[1]
    user_id = query.from_user.id

    if action == "join":
        joined_seller = await join_deal_seller(user_id, deal_id)
        joined_buyer = await join_deal_buyer(user_id, deal_id)
        if joined_seller or joined_buyer:
            await query.reply_text("Joined the deal successfully!")
        else:
            await query.reply_text("You are not part of this deal.")
    elif action == "start" and user_id in ADMIN_IDS:
        res = await start_deal(context.bot, deal_id)
        await query.reply_text(res)
    elif action == "cancel" and user_id in ADMIN_IDS:
        res = await cancel_deal(context.bot, deal_id)
        await query.reply_text(res)
    else:
        await query.reply_text("You are not authorized to perform this action.")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), submit_form))
app.add_handler(CallbackQueryHandler(button_handler))
app.run_polling()
