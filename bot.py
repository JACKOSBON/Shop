import os
import asyncio
import re
import random
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, InviteHashInvalidError, InviteHashExpiredError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── CUSTOM MESSAGE ──────────────────────────────────────────
SPAM_MESSAGE = """
💰 FREE CARDING CLASSES AND REWARDS DAILY 💰
WE ARE BACK CARDERS HUB
JOIN FAST: @carders_hub07
"""

SPAM_INTERVAL = 300  # 5 minutes
MAX_GROUPS = 150

# ─── GLOBAL VARIABLES ──────────────────────────────────────
visited_groups = set()
pending_links = []
group_counter = 0
spam_count = 0
spam_running = True  # Flag to control spam

client = None

# ─── COMMAND: /start ──────────────────────────────────────
async def start_cmd(event):
    await event.reply(
        "🤖 **Timed Spam Bot Active!**\n\n"
        "📤 Sends spam every 5 minutes to joined groups.\n\n"
        "Commands:\n"
        "/join <link> - Join & spam a group\n"
        "/add <link> - Add link to queue\n"
        "/status - Check bot status\n"
        "/startspam - Start auto-spam\n"
        "/stopspam - Stop auto-spam\n"
        "/help - Show this message\n\n"
        "Example: `/join https://t.me/carders_hub07`"
    )

# ─── COMMAND: /join ──────────────────────────────────────
async def join_cmd(event):
    global pending_links
    text = event.raw_text
    links = re.findall(r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+', text)
    
    if not links:
        await event.reply("❌ No valid link found.\nUsage: `/join https://t.me/group`")
        return
    
    added = []
    for link in links:
        if link not in pending_links and link not in visited_groups:
            pending_links.append(link)
            added.append(link)
    
    await event.reply(f"✅ Added {len(added)} link(s) to queue.")

# ─── COMMAND: /add ──────────────────────────────────────
async def add_cmd(event):
    global pending_links
    text = event.raw_text
    links = re.findall(r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+', text)
    
    if not links:
        await event.reply("❌ No valid link found.\nUsage: `/add https://t.me/group`")
        return
    
    added = []
    for link in links:
        if link not in pending_links and link not in visited_groups:
            pending_links.append(link)
            added.append(link)
    
    await event.reply(f"✅ Added {len(added)} link(s) to queue.")

# ─── COMMAND: /status ──────────────────────────────────────
async def status_cmd(event):
    global group_counter, spam_count, pending_links, spam_running
    await event.reply(
        f"📊 **Bot Status**\n\n"
        f"📌 Queue: {len(pending_links)} links\n"
        f"✅ Joined: {group_counter} groups\n"
        f"📤 Total spam sent: {spam_count} times\n"
        f"⏱️ Interval: {SPAM_INTERVAL} seconds\n"
        f"🔄 Spam: {'🟢 Running' if spam_running else '🔴 Stopped'}\n"
        f"📝 Message: {SPAM_MESSAGE[:40]}..."
    )

# ─── COMMAND: /startspam ──────────────────────────────────
async def start_spam_cmd(event):
    global spam_running
    spam_running = True
    await event.reply("✅ **Auto-spam started!** Bot will send messages every 5 minutes.")

# ─── COMMAND: /stopspam ──────────────────────────────────
async def stop_spam_cmd(event):
    global spam_running
    spam_running = False
    await event.reply("⏸️ **Auto-spam stopped!** Use `/startspam` to resume.")

# ─── COMMAND: /help ──────────────────────────────────────
async def help_cmd(event):
    await event.reply(
        "📖 **Commands:**\n\n"
        "/start - Welcome message\n"
        "/join <link> - Join group & add to spam list\n"
        "/add <link> - Add link to queue\n"
        "/status - Check bot status\n"
        "/startspam - Start auto-spam\n"
        "/stopspam - Stop auto-spam\n"
        "/help - Show this message\n\n"
        "Example: `/join https://t.me/carders_hub07`"
    )

# ─── AUTO-SPAM FUNCTION ──────────────────────────────────
async def auto_spam():
    global client, spam_count, spam_running
    print("⏳ Auto-spam thread started...")
    
    while True:
        if spam_running:
            try:
                dialogs = await client.get_dialogs()
                groups = [d for d in dialogs if d.is_group or d.is_channel]
                
                if not groups:
                    print("⚠️ No groups found. Add some using /join")
                    await asyncio.sleep(SPAM_INTERVAL)
                    continue
                
                random.shuffle(groups)
                sent_this_cycle = 0
                
                for dialog in groups[:50]:
                    try:
                        await client.send_message(dialog.entity, SPAM_MESSAGE)
                        spam_count += 1
                        sent_this_cycle += 1
                        print(f"📤 Spam #{spam_count} sent to: {dialog.title or dialog.id}")
                        await asyncio.sleep(random.uniform(5, 15))
                    except FloodWaitError as e:
                        print(f"⏳ Flood wait: {e.seconds}s")
                        await asyncio.sleep(e.seconds + 5)
                    except Exception as e:
                        print(f"❌ Send failed: {e}")
                
                print(f"✅ Spam cycle complete. Sent to {sent_this_cycle} groups. Next in {SPAM_INTERVAL}s")
                await asyncio.sleep(SPAM_INTERVAL)
                
            except Exception as e:
                print(f"⚠️ Auto-spam error: {e}")
                await asyncio.sleep(SPAM_INTERVAL)
        else:
            print("⏸️ Spam paused. Waiting...")
            await asyncio.sleep(10)

# ─── AUTO-JOIN QUEUE PROCESSOR ──────────────────────────
async def join_processor():
    global client, pending_links, visited_groups, group_counter, spam_count
    print("🔄 Join processor started...")
    
    while True:
        if pending_links and group_counter < MAX_GROUPS:
            link = pending_links.pop(0)
            if link in visited_groups:
                continue
            
            print(f"🔄 Joining: {link}")
            try:
                if "t.me/joinchat/" in link or "t.me/+" in link:
                    hash_part = link.split("/")[-1]
                    await client(ImportChatInviteRequest(hash_part))
                elif "t.me/" in link:
                    username = link.split("t.me/")[-1].split("/")[0]
                    await client(JoinChannelRequest(username))
                else:
                    continue
                
                visited_groups.add(link)
                group_counter += 1
                print(f"✅ Joined: {link} (Total: {group_counter})")
                
                # Send welcome spam
                entity = await client.get_entity(link)
                await client.send_message(entity, SPAM_MESSAGE)
                spam_count += 1
                print(f"📤 First spam sent to new group")
                
            except FloodWaitError as e:
                print(f"⏳ Flood wait: {e.seconds}s")
                pending_links.insert(0, link)
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                print(f"❌ Failed: {e}")
            
            await asyncio.sleep(random.uniform(10, 30))
        else:
            await asyncio.sleep(30)

# ─── MAIN ──────────────────────────────────────────────────
async def main():
    global client, pending_links
    
    print("🚀 Timed Spam Bot Starting...")
    print(f"📝 Message: {SPAM_MESSAGE[:50]}...")
    print(f"⏱️ Interval: {SPAM_INTERVAL} seconds")
    
    # Create client INSIDE async main
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    print("✅ Bot logged in!")
    
    # Load manual links from file
    if os.path.exists("links.txt"):
        with open("links.txt", "r") as f:
            for line in f:
                link = line.strip()
                if link and link not in pending_links:
                    pending_links.append(link)
                    print(f"📌 Loaded from file: {link}")
    
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
    
    print("🤖 Bot is ready! Send /start on Telegram.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
