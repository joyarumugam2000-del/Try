# copy this to config.py and update values
import os

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8009833248:AAFGG6NnHPzQdg0nRxf4PaGVVpzwyhKgbLg")

# Channel (or group) ID where logs will be posted. Use numeric ID (e.g., -1001234567890).
# If you don't want logging, set to 0 or leave as default 0.
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1002412313028"))

# Path to SQLite DB
DB_PATH = os.getenv("DB_PATH", "bot_database.sqlite3")

# Time format for display (UTC)
TIME_FORMAT = os.getenv("TIME_FORMAT", "%d-%m-%Y %I:%M:%S %p UTC")
