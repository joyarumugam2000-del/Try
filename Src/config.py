import os
from dotenv import load_dotenv

# Load from .env file if present
load_dotenv()

# --- BOT CREDENTIALS ---
# Your bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8009833248:AAFGG6NnHPzQdg0nRxf4PaGVVpzwyhKgbLg")

# Optional (only needed if you later use Pyrogram/Telethon APIs)
API_ID = os.getenv("API_ID", "your_api_id")
API_HASH = os.getenv("API_HASH", "your_api_hash")

# --- OWNER & LOGGING ---
# Owner has full rights
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 1798791768))
# Channel/group where all logs will be saved
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", -1002412313028))

# --- DVA / ESCROW SETTINGS ---
# Group where escrow/DVA deals happen (numeric ID, not invite link!)
DVA_GROUP_ID = int(os.getenv("DVA_GROUP_ID", -1002219275732))
# Escrow fee rate (1% = 0.01)
ESCROW_FEE_RATE = float(os.getenv("ESCROW_FEE_RATE", 0.01))

# --- ANTI-SCAM SETTINGS ---
# Username similarity threshold (0-100, higher = stricter)
SIMILARITY_THRESHOLD = int(os.getenv("SIMILARITY_THRESHOLD", 85))

# --- OTHER SETTINGS ---
# DB file path (SQLite)
DB_PATH = os.getenv("DB_PATH", "bot.db")
# How long before kicking user after deal close alert (seconds)
AUTO_KICK_DELAY = int(os.getenv("AUTO_KICK_DELAY", 300))  # 5 minutes
