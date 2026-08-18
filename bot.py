import os
import asyncio
import random
import re
import time
from telethon import TelegramClient, functions, types
from telethon.errors import FloodWaitError, InviteHashInvalidError, InviteHashExpiredError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE_NUMBER")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Spam messages (rotate automatically)
SPAM_MESSAGES = [
    """
🎁 **FREE $5 USDT AIRDROP!** 🎁
Claim now: https://fr33usdtbot.onrender.com
Limited time offer! 🚀
""",
    """
💰 **FREE CARDING CLASSES AND REWARDS DAILY** 💰
WE ARE BACK CARDERS HUB
JOIN FAST: @carders_hub07
""",
    """
🔥 **JOIN THE BIGGEST CARDING COMMUNITY** 🔥
Daily rewards, classes, and more!
👉 @carders_hub07
"""
]

# Seed groups to start with
SEED_GROUPS = [
    "https://t.me/carders_hub07",
    "https://t.me/crypto_airdrop_chat",
    "https://t.me/defi_discussion",
    "https://t.me/bitcoin_talk"
]

visited_groups = set()
pending_links = []
group_counter = 0
MAX_GROUPS = 150

client = TelegramClient('spam_bot_session', API_ID, API_HASH)

async def join_group(link):
    global group_counter
    try:
        if "t.me/joinchat/" in link or "t.me/+" in link:
            hash_part = link.split("/")[-1]
            await client(ImportChatInviteRequest(hash_part))
        elif "t.me/" in link:
            username = link.split("t.me/")[-1].split("/")[0]
            await client(JoinChannelRequest(username))
        else:
            return False
        group_counter += 1
        print(f"✅ Joined: {link} (Total: {group_counter})")
        await asyncio.sleep(random.uniform(5, 15))
        return True
    except FloodWaitError as e:
        print(f"⏳ Flood wait: {e.seconds}s")
        await asyncio.sleep(e.seconds + 10)
        return False
    except Exception as e:
        print(f"❌ Failed: {link} -> {e}")
        return False

async def send_spam(group_entity):
    try:
        msg = random.choice(SPAM_MESSAGES)
        await client.send_message(group_entity, msg, parse_mode='markdown')
        print(f"📤 Spam sent to: {group_entity.title or group_entity.id}")
        await asyncio.sleep(random.uniform(8, 20))
        return True
    except FloodWaitError as e:
        print(f"⏳ Flood wait: {e.seconds}s")
        await asyncio.sleep(e.seconds + 10)
        return False
    except Exception as e:
        print(f"❌ Send failed: {e}")
        return False

async def extract_links(group_entity):
    links = []
    try:
        async for msg in client.iter_messages(group_entity, limit=30):
            if msg.text:
                pattern = r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+'
                found = re.findall(pattern, msg.text)
                for link in found:
                    if not link.startswith('http'):
                        link = 'https://' + link
                    if link not in visited_groups and link not in pending_links:
                        links.append(link)
                        pending_links.append(link)
                        print(f"🔗 Found: {link}")
    except Exception as e:
        print(f"⚠️ Scrape error: {e}")
    return links

async def main():
    global pending_links
    print("🚀 Auto-Spam Bot Starting...")
    await client.start(phone=PHONE)
    print("✅ Logged in!")

    for link in SEED_GROUPS:
        if link not in pending_links:
            pending_links.append(link)

    while pending_links and group_counter < MAX_GROUPS:
        link = pending_links.pop(0)
        if link in visited_groups:
            continue

        print(f"🔄 Joining: {link}")
        success = await join_group(link)
        if success:
            visited_groups.add(link)
            try:
                entity = await client.get_entity(link)
                await send_spam(entity)
                new_links = await extract_links(entity)
                print(f"📌 Found {len(new_links)} new links")
            except Exception as e:
                print(f"⚠️ Error with group: {e}")

        delay = random.uniform(20, 60)
        print(f"⏳ Waiting {int(delay)}s...")
        await asyncio.sleep(delay)

    print(f"✅ Done! Joined {group_counter} groups.")

if __name__ == "__main__":
    asyncio.run(main())
