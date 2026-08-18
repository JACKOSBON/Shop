import os
import asyncio
import re
import random
import time
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

# ─── CONFIG ──────────────────────────────────────────────────
SPAM_INTERVAL = 300  # 5 minutes (300 seconds)
MAX_GROUPS = 150     # Max groups to spam

# ─── GLOBAL VARIABLES ──────────────────────────────────────
visited_groups = set()
pending_links = []
group_counter = 0
spam_count = 0

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ─── COMMAND: /start ──────────────────────────────────────
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🤖 **Timed Spam Bot Active!**\n\n"
        "📤 Sends spam every 5 minutes to joined groups.\n\n"
        "Commands:\n"
        "/join <link> - Join & spam a group\n"
        "/join <link1> <link2> - Join multiple groups\n"
        "/add <link> - Add link to queue\n"
        "/status - Check bot status\n"
        "/stopspam - Stop auto-spam\n"
        "/startspam - Start auto-spam\n"
        "/help - Show this message\n\n"
        "Example: `/join https://t.me/carders_hub07`"
    )

# ─── COMMAND: /join ──────────────────────────────────────
@client.on(events.NewMessage(pattern='/join'))
async def join_command(event):
    global pending_links, group_counter
    text = event.raw_text
    links = re.findall(r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+', text)
    
    if not links:
        await event.reply("❌ No valid link found.\nUsage: `/join https://t.me/group`")
        return
    
    await event.reply(f"🔄 Processing {len(links)} link(s)...")
    
    results = []
    for link in links:
        if link in visited_groups:
            results.append(f"⏩ Already joined: {link}")
            continue
        if link in pending_links:
            results.append(f"⏳ Already in queue: {link}")
            continue
        
        pending_links.append(link)
        results.append(f"📌 Added to queue: {link}")
    
    await event.reply("\n".join(results))

# ─── COMMAND: /add ──────────────────────────────────────
@client.on(events.NewMessage(pattern='/add'))
async def add_command(event):
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
@client.on(events.NewMessage(pattern='/status'))
async def status(event):
    await event.reply(
        f"📊 **Bot Status**\n\n"
        f"📌 Queue: {len(pending_links)} links\n"
        f"✅ Joined: {group_counter} groups\n"
        f"📤 Spam sent: {spam_count} times\n"
        f"⏱️ Interval: {SPAM_INTERVAL} seconds"
    )

# ─── COMMAND: /help ──────────────────────────────────────
@client.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(
        "📖 **Commands:**\n\n"
        "/start - Welcome message\n"
        "/join <link> - Join group & add to spam list\n"
        "/add <link> - Add link to queue\n"
        "/status - Check bot status\n"
        "/stopspam - Stop auto-spam\n"
        "/startspam - Start auto-spam\n"
        "/help - Show this message\n\n"
        "Example: `/join https://t.me/carders_hub07`"
    )

# ─── AUTO-SPAM FUNCTION ──────────────────────────────────
async def auto_spam():
    global group_counter, spam_count
    print("⏳ Auto-spam thread started...")
    
    while True:
        try:
            # Get all groups where bot is member
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            if not groups:
                print("⚠️ No groups found. Add some using /join")
                await asyncio.sleep(SPAM_INTERVAL)
                continue
            
            # Shuffle groups to avoid pattern
            random.shuffle(groups)
            
            # Send spam to each group
            for dialog in groups[:50]:  # Limit to 50 per cycle
                try:
                    await client.send_message(dialog.entity, SPAM_MESSAGE)
                    spam_count += 1
                    print(f"📤 Spam #{spam_count} sent to: {dialog.title or dialog.id}")
                    await asyncio.sleep(random.uniform(5, 15))  # Delay between groups
                except FloodWaitError as e:
                    print(f"⏳ Flood wait: {e.seconds}s")
                    await asyncio.sleep(e.seconds + 5)
                except Exception as e:
                    print(f"❌ Send failed: {e}")
            
            print(f"✅ Spam cycle complete. Next in {SPAM_INTERVAL}s")
            await asyncio.sleep(SPAM_INTERVAL)
            
        except Exception as e:
            print(f"⚠️ Auto-spam error: {e}")
            await asyncio.sleep(SPAM_INTERVAL)

# ─── AUTO-JOIN QUEUE PROCESSOR ──────────────────────────
async def join_processor():
    global pending_links, visited_groups, group_counter
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
                
                # Send welcome spam immediately
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
    print("🚀 Timed Spam Bot Starting...")
    print(f"📝 Message: {SPAM_MESSAGE[:50]}...")
    print(f"⏱️ Interval: {SPAM_INTERVAL} seconds")
    
    # Load manual links from file
    if os.path.exists("links.txt"):
        with open("links.txt", "r") as f:
            for line in f:
                link = line.strip()
                if link and link not in pending_links:
                    pending_links.append(link)
                    print(f"📌 Loaded from file: {link}")
    
    # Start background tasks
    asyncio.create_task(auto_spam())
    asyncio.create_task(join_processor())
    
    # Start bot
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
