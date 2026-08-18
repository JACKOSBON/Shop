# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Optional — for bot account

# Message to spam
SPAM_MESSAGE = """
🎁 **FREE CARDING CLASSES AND REWARDS DAILY 
WE ARE BACK CARDERS HUB JOIN FAST @carders_hub07
"""

# Words to detect group links
LINK_KEYWORDS = ["t.me/", "telegram.me/", "https://t.me/", "joinchat"]
