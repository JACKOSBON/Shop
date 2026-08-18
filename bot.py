# bot.py
import asyncio
import re
import random
import time
from telethon import TelegramClient, events, functions, types
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import FloodWaitError, InviteHashInvalidError, InviteHashExpiredError
from config import *
import os

# Initialize client
client = TelegramClient('spam_bot_session', API_ID, API_HASH)

# Store visited groups and pending links
visited_groups = set()
pending_links = []
group_counter = 0
max_groups = 100  # Limit to avoid ban

async def join_group(link):
    """Join a Telegram group using invite link"""
    global group_counter
    try:
        if "t.me/joinchat/" in link or "t.me/+" in link:
            # Private group with hash
            hash_part = link.split("/")[-1]
            await client(ImportChatInviteRequest(hash_part))
        elif "t.me/" in link:
            # Public group or username
            username = link.split("t.me/")[-1]
            if "/" in username:
                username = username.split("/")[0]
            await client(JoinChannelRequest(username))
        else:
            return False
        
        group_counter += 1
        print(f"✅ Joined: {link} (Total: {group_counter})")
        await asyncio.sleep(random.uniform(3, 7))  # Random delay to avoid ban
        return True
    except FloodWaitError as e:
        print(f"⏳ Flood wait: {e.seconds} seconds")
        await asyncio.sleep(e.seconds + 5)
        return False
    except (InviteHashInvalidError, InviteHashExpiredError):
        print(f"❌ Invalid/Expired link: {link}")
        return False
    except Exception as e:
        print(f"❌ Error joining {link}: {e}")
        return False

async def send_spam_message(group_entity):
    """Send spam message to a group"""
    try:
        await client.send_message(group_entity, SPAM_MESSAGE, parse_mode='markdown')
        print(f"📤 Spam sent to: {group_entity.title or group_entity.id}")
        await asyncio.sleep(random.uniform(5, 12))
        return True
    except FloodWaitError as e:
        print(f"⏳ Flood wait: {e.seconds} seconds")
        await asyncio.sleep(e.seconds + 5)
        return False
    except Exception as e:
        print(f"❌ Failed to send spam: {e}")
        return False

async def extract_links_from_group(group_entity):
    """Scrape messages in group to find invite links"""
    links = []
    try:
        async for message in client.iter_messages(group_entity, limit=50):
            if message.text:
                # Find all Telegram invite links
                for keyword in LINK_KEYWORDS:
                    if keyword in message.text.lower():
                        # Extract links using regex
                        pattern = r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[\w\-_]+'
                        found_links = re.findall(pattern, message.text)
                        for link in found_links:
                            if not link.startswith('http'):
                                link = 'https://' + link
                            if link not in visited_groups and link not in pending_links:
                                links.append(link)
                                pending_links.append(link)
                                print(f"🔗 Found new link: {link}")
    except Exception as e:
        print(f"⚠️ Could not scrape {group_entity.title}: {e}")
    return links

async def main():
    global pending_links, visited_groups
    
    print("🚀 Starting Spam Bot...")
    await client.start(phone=PHONE_NUMBER)
    print("✅ Logged in successfully!")
    
    # Start with some seed groups
    seed_groups = [
        "https://t.me/crypto_airdrop_chat",
        "https://t.me/defi_discussion",
        "https://t.me/bitcoin_talk",
        "https://t.me/ethereum_news"
    ]
    
    for link in seed_groups:
        if link not in pending_links:
            pending_links.append(link)
    
    while pending_links and group_counter < max_groups:
        # Get next link from queue
        current_link = pending_links.pop(0)
        
        if current_link in visited_groups:
            continue
        
        # Join the group
        print(f"🔄 Joining: {current_link}")
        success = await join_group(current_link)
        
        if success:
            visited_groups.add(current_link)
            group_entity = await client.get_entity(current_link)
            
            # Send spam message
            await send_spam_message(group_entity)
            
            # Extract more links from this group
            new_links = await extract_links_from_group(group_entity)
            print(f"📌 Found {len(new_links)} new links from this group")
            
            # Leave group after spamming (optional)
            # await client(functions.channels.LeaveChannelRequest(group_entity))
            # print(f"👋 Left group: {group_entity.title}")
        
        # Random delay to avoid detection
        delay = random.uniform(15, 45)
        print(f"⏳ Waiting {int(delay)} seconds...")
        await asyncio.sleep(delay)
    
    print(f"✅ Done! Joined {group_counter} groups.")

if __name__ == "__main__":
    asyncio.run(main())
