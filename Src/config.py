import os

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8009833248:AAFGG6NnHPzQdg0nRxf4PaGVVpzwyhKgbLg")

# DVA Deal Group (where active deals are posted/managed)
DVA_GROUP_ID = int(os.getenv("DVA_GROUP_ID", "-1002841591689"))

# Permanent invite link for the DVA Deal Group
DVA_INVITE_LINK = os.getenv("DVA_INVITE_LINK", "https://t.me/+GCPImadK3e03M2I1")

# Channel (or group) ID where logs will be posted
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1002412313028"))

# Admins: list of Telegram user IDs who can start/cancel deals
ADMIN_IDS = [123456789, 987654321]  # replace with your admin IDs

# Kick delay in seconds (e.g., 30 minutes)
KICK_DELAY = int(os.getenv("KICK_DELAY", 1800))
