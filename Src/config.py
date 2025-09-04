import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0") or 0)
DVA_GROUP_ID = int(os.getenv("DVA_GROUP_ID", "0") or 0)

TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID") or ""
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH") or ""

DB_PATH = os.getenv("DB_PATH", "bot.db")
ESCROW_FEE_RATE = float(os.getenv("ESCROW_FEE_RATE", "0.01"))  # 1%
KICK_AFTER_SECONDS = int(os.getenv("KICK_AFTER_SECONDS", "300"))  # 5 minutes
MIN_SIMILARITY = int(os.getenv("MIN_SIMILARITY", "86"))  # Rapidfuzz ratio threshold
