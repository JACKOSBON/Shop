import os
import asyncio
import re
import random
import time
import logging
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, InviteHashInvalidError, InviteHashExpiredError, RPCError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from dotenv import load_dotenv

load_dotenv()

# ─── LOGGING ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── CONFIG ──────────────────────────────────────────────
SPAM_MESSAGE = """
💰 FREE CARDING CLASSES AND REWARDS DAILY 💰
WE ARE BACK CARDERS HUB
JOIN FAST: @carders_hub07
"""

SPAM_INTERVAL = 300  # 5 minutes
MAX_GROUPS = 200
RECONNECT_DELAY = 10

# ─── GLOBALS ──────────────────────────────────────────────
joined_groups = {}
pending_links = []
spam_count = 0
spam_running = True
client = None

# ─── COMMANDS ──────────────────────────────────────────────
async def start_cmd(event):
    await event.reply(
        "🤖 **Spam Bot Active!**\n\n"
        "📤 Sends spam every 5 minutes to joined groups.\n\n"
        "Commands:\n"
        "/join <link> - Join & spam a group\n"
        "/add <link> - Add link to queue\n"
        "/status - Check bot status\n"
        "/startspam - Start auto-spam\n"
        "/stopspam - Stop auto-spam\n"
        "/help - Show this message"
    )

async def join_cmd(event):
    global pending_links
    text = event.raw_text
    links = re.findall(r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+', text)
    
    if not links:
        await event.reply("❌ No valid link found.\nUsage: `/join https://t.me/group`")
        return
    
    added = []
    for link in links:
        if link not in pending_links:
            pending_links.append(link)
            added.append(link)
    
    await event.reply(f"✅ Added {len(added)} link(s) to queue.\nBot will join and spam automatically.")

async def add_cmd(event):
    global pending_links
    text = event.raw_text
    links = re.findall(r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+', text)
    
    if not links:
        await event.reply("❌ No valid link found.\nUsage: `/add https://t.me/group`")
        return
    
    added = []
    for link in links:
        if link not in pending_links:
            pending_links.append(link)
            added.append(link)
    
    await event.reply(f"✅ Added {len(added)} link(s) to queue.")

async def status_cmd(event):
    global joined_groups, spam_count, pending_links, spam_running
    await event.reply(
        f"📊 **Bot Status**\n\n"
        f"📌 Queue: {len(pending_links)} links\n"
        f"✅ Joined groups: {len(joined_groups)}\n"
        f"📤 Total spam sent: {spam_count}\n"
        f"⏱️ Interval: {SPAM_INTERVAL}s\n"
        f"🔄 Spam: {'🟢 Running' if spam_running else '🔴 Stopped'}\n"
        f"📝 Message: {SPAM_MESSAGE[:40]}..."
    )

async def start_spam_cmd(event):
    global spam_running
    spam_running = True
    await event.reply("✅ **Auto-spam started!**")

async def stop_spam_cmd(event):
    global spam_running
    spam_running = False
    await event.reply("⏸️ **Auto-spam stopped!**")

async def help_cmd(event):
    await event.reply(
        "📖 **Commands:**\n\n"
        "/start - Welcome\n"
        "/join <link> - Join & spam group\n"
        "/add <link> - Add link to queue\n"
        "/status - Bot status\n"
        "/startspam - Start auto-spam\n"
        "/stopspam - Stop auto-spam\n"
        "/help - This message"
    )

# ─── JOIN GROUP ──────────────────────────────────────────────
async def join_and_spam(link):
    global joined_groups, spam_count
    try:
        if "t.me/joinchat/" in link or "t.me/+" in link:
            hash_part = link.split("/")[-1]
            await client(ImportChatInviteRequest(hash_part))
        elif "t.me/" in link:
            username = link.split("t.me/")[-1].split("/")[0]
            await client(JoinChannelRequest(username))
        else:
            return False, "Invalid link format"
        
        entity = await client.get_entity(link)
        joined_groups[entity.id] = entity
        await client.send_message(entity, SPAM_MESSAGE)
        spam_count += 1
        logger.info(f"✅ Joined & spammed: {entity.title or entity.id}")
        return True, f"Joined & spammed: {entity.title or entity.id}"
        
    except FloodWaitError as e:
        logger.warning(f"⏳ Flood wait: {e.seconds}s")
        return False, f"Flood wait {e.seconds}s"
    except (InviteHashInvalidError, InviteHashExpiredError):
        return False, "Invalid/Expired link"
    except Exception as e:
        logger.error(f"❌ Join error: {e}")
        return False, f"Error: {str(e)[:50]}"

# ─── BACKGROUND TASKS ──────────────────────────────────────
async def join_processor():
    global pending_links
    logger.info("🔄 Join processor started")
    while True:
        try:
            if pending_links:
                link = pending_links.pop(0)
                logger.info(f"🔄 Processing: {link}")
                success, msg = await join_and_spam(link)
                logger.info(f"📌 Result: {msg}")
                await asyncio.sleep(random.uniform(10, 30))
            else:
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"⚠️ Join processor error: {e}")
            await asyncio.sleep(30)

async def auto_spam():
    global client, spam_count, spam_running, joined_groups
    logger.info("⏳ Auto-spam thread started")
    
    while True:
        try:
            if spam_running and joined_groups:
                groups = list(joined_groups.values())
                random.shuffle(groups)
                sent = 0
                
                for group in groups[:50]:
                    try:
                        await client.send_message(group, SPAM_MESSAGE)
                        spam_count += 1
                        sent += 1
                        logger.info(f"📤 Spam #{spam_count} sent to: {group.title or group.id}")
                        await asyncio.sleep(random.uniform(5, 15))
                    except FloodWaitError as e:
                        logger.warning(f"⏳ Flood wait: {e.seconds}s")
                        await asyncio.sleep(e.seconds + 5)
                    except Exception as e:
                        logger.error(f"❌ Send failed: {e}")
                
                logger.info(f"✅ Spam cycle complete. Sent to {sent} groups. Next in {SPAM_INTERVAL}s")
                await asyncio.sleep(SPAM_INTERVAL)
            else:
                if not spam_running:
                    logger.info("⏸️ Spam paused")
                elif not joined_groups:
                    logger.info("⚠️ No groups to spam. Use /join")
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"⚠️ Auto-spam error: {e}")
            await asyncio.sleep(SPAM_INTERVAL)

# ─── KEEP-ALIVE ──────────────────────────────────────────────
async def keep_alive():
    """Send a ping to keep Render worker alive"""
    while True:
        try:
            logger.info("💓 Keep-alive ping")
            await client.send_message("me", "💓 Bot is alive")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")
        await asyncio.sleep(1800)  # 30 minutes

# ─── MAIN ──────────────────────────────────────────────────
async def main():
    global client, pending_links
    
    logger.info("🚀 Bot Starting...")
    logger.info(f"📝 Message: {SPAM_MESSAGE[:50]}...")
    logger.info(f"⏱️ Interval: {SPAM_INTERVAL}s")
    
    # Create client
    client = TelegramClient('bot_session', API_ID, API_HASH)
    
    # Connect with auto-reconnect
    while True:
        try:
            await client.start(bot_token=BOT_TOKEN)
            logger.info("✅ Bot logged in!")
            break
        except Exception as e:
            logger.error(f"❌ Login failed: {e}. Retrying in {RECONNECT_DELAY}s...")
            await asyncio.sleep(RECONNECT_DELAY)
    
    # Load manual links
    if os.path.exists("links.txt"):
        with open("links.txt", "r") as f:
            for line in f:
                link = line.strip()
                if link and link not in pending_links:
                    pending_links.append(link)
                    logger.info(f"📌 Loaded from file: {link}")
    
    # Register handlers
    client.add_event_handler(start_cmd, events.NewMessage(pattern='/start'))
    client.add_event_handler(join_cmd, events.NewMessage(pattern='/join'))
    client.add_event_handler(add_cmd, events.NewMessage(pattern='/add'))
    client.add_event_handler(status_cmd, events.NewMessage(pattern='/status'))
    client.add_event_handler(start_spam_cmd, events.NewMessage(pattern='/startspam'))
    client.add_event_handler(stop_spam_cmd, events.NewMessage(pattern='/stopspam'))
    client.add_event_handler(help_cmd, events.NewMessage(pattern='/help'))
    
    # Start background tasks
    asyncio.create_task(auto_spam())
    asyncio.create_task(join_processor())
    asyncio.create_task(keep_alive())
    
    logger.info("🤖 Bot is ready! Send /start on Telegram.")
    
    # Run with auto-reconnect
    while True:
        try:
            await client.run_until_disconnected()
        except (ConnectionError, RPCError) as e:
            logger.error(f"⚠️ Connection lost: {e}. Reconnecting...")
            await asyncio.sleep(RECONNECT_DELAY)
            try:
                await client.connect()
                logger.info("✅ Reconnected!")
            except Exception as reconnect_error:
                logger.error(f"❌ Reconnect failed: {reconnect_error}")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
            await asyncio.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
