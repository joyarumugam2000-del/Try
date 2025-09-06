import os

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8009833248:AAFGG6NnHPzQdg0nRxf4PaGVVpzwyhKgbLg")

# DVA Deal Group (where active deals are posted/managed)
DVA_GROUP_ID = int(os.getenv("DVA_GROUP_ID", "-1002841591689"))  

# Permanent invite link for the DVA Deal Group
DVA_INVITE_LINK = os.getenv("DVA_INVITE_LINK", "https://t.me/+GCPImadK3e03M2I1")

# Channel (or group) ID where logs will be posted
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1002412313028"))

# Path to SQLite DB (will auto-create if not present)
DB_PATH = os.getenv("DB_PATH", "./dva.db")

# Optional: Always treat these users as admins (comma-separated numeric user_ids)
ADMIN_USER_IDS = [int(uid) for uid in os.getenv("ADMIN_USER_IDS", "").split(",") if uid.strip()]

# Timezone for all timestamps (IST in your case)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# Background poll interval to check for deal close → auto-kick (in seconds)
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))
