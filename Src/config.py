import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# 🔹 Core bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))

# 🔹 Groups & logging
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
DVA_GROUP_ID = int(os.getenv("DVA_GROUP_ID", "0"))

# 🔹 Escrow / anti-scam settings
ESCROW_FEE_RATE = float(os.getenv("ESCROW_FEE_RATE", "0.01"))  # default 1%
SIMILARITY_THRESHOLD = int(os.getenv("SIMILARITY_THRESHOLD", "85"))  # fuzzy username check
AUTO_KICK_DELAY = int(os.getenv("AUTO_KICK_DELAY", "300"))  # 5 minutes

# 🔹 Database
DB_PATH = os.getenv("DB_PATH", "bot.db")

# ✅ Backwards compatibility (so main.py still works)
OWNER_ID = BOT_OWNER_ID
