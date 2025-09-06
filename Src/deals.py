from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import generate_deal_id, kick_users_after_delay
from db import add_deal, get_deal, update_deal
from config import DVA_GROUP_ID, KICK_DELAY
import asyncio

def create_deal_buttons(deal_id, seller_id, buyer_id):
    # Buttons will be filtered by callback handler
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Join Deal", callback_data=f"join_{deal_id}")],
        [InlineKeyboardButton("🟢 Start Deal", callback_data=f"start_{deal_id}")],
        [InlineKeyboardButton("❌ Cancel Deal", callback_data=f"cancel_{deal_id}")]
    ])

async def post_deal(bot, seller, buyer, amount, details):
    deal_id = generate_deal_id()
    add_deal(deal_id, seller, buyer, amount, details)
    text = f"New Deal Request\nSeller: @{seller}\nBuyer: @{buyer}\nAmount: {amount}\nDetails: {details}"
    buttons = create_deal_buttons(deal_id, seller, buyer)
    await bot.send_message(chat_id=DVA_GROUP_ID, text=text, reply_markup=buttons)
    return deal_id

async def start_deal(bot, deal_id):
    deal = get_deal(deal_id)
    if deal[6] and deal[7]:  # both joined
        update_deal(deal_id, status="active")
        await bot.send_message(DVA_GROUP_ID, f"Deal Started!\nDeal ID: {deal_id}\nSeller: @{deal[1]}\nBuyer: @{deal[2]}\nAmount: {deal[3]}")
        asyncio.create_task(kick_users_after_delay(bot, DVA_GROUP_ID, [int(deal[1]), int(deal[2])], KICK_DELAY))
        return "Deal started successfully"
    return "Cannot start deal: both users have not joined"

async def cancel_deal(bot, deal_id):
    deal = get_deal(deal_id)
    if deal:
        update_deal(deal_id, status="canceled")
        await bot.send_message(DVA_GROUP_ID, f"Deal {deal_id} canceled by admin.")
        return "Deal canceled successfully"
    return "Deal not found"
