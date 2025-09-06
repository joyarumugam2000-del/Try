import random, string
import asyncio

def generate_deal_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def kick_users_after_delay(bot, group_id, users, delay=1800):
    await asyncio.sleep(delay)
    for user in users:
        try:
            await bot.ban_chat_member(group_id, user)
        except:
            pass
