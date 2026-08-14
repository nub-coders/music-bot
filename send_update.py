#!/usr/bin/env python3
"""
send_update.py — Send release/update summary with custom emojis to a user or chat.
"""
import os
import sys
import asyncio
import argparse
from dotenv import load_dotenv

load_dotenv()

from pyrogram import Client
from utils.emoji import EmojiTag
from config import API_ID, API_HASH, BOT_TOKEN as CONFIG_BOT_TOKEN


MESSAGE_TEMPLATE = f"""<u><b>{EmojiTag.ROCKET} | ᴄʜᴀɴɢᴇs sɪɴᴄᴇ 2ᴄᴇ88ꜰ5</b></u>

<b>{EmojiTag.ROCKET} ɴᴇᴡ ꜰᴇᴀᴛᴜʀᴇs:</b>
• <b>Hybrid Autoplay & Suggestions:</b> Suggests 5 related tracks via YouTube Music Radio Mix when queue ends, with a 5s countdown timer & <code>/autoplay</code> toggle.
• <b>Direct Stream URLs:</b> Direct HTTP/HTTPS audio/video and HLS/m3u8 stream links can now be played directly.
• <b>Custom Emoji System:</b> Added Telegram custom emoji styling across all bot messages and buttons.

<b>{EmojiTag.SPARKLE_STAR} ɪᴍᴘʀᴏᴠᴇᴍᴇɴᴛs:</b>
• <b>Non-Blocking Now-Playing Cards:</b> Instant playback notification with async photo card swap and deterministic caching per track.
• <b>Queue Visuals:</b> Generates a sleek dark-gradient queue card image with Poppins font.
• <b>Admin Controls:</b> Autoplay settings & suggestion cards restricted to admins/auth users.

<b>{EmojiTag.WARNING} ʙᴜɢ ꜰɪxᴇs:</b>
• <b>Skip Permission Bypass:</b> Restricted "Play Now" queue button and <code>/play -f</code> to admins or song owner.
• <b>Telegram Entity Fixes:</b> HTML-escaped song titles and fixed custom emoji rendering for tens queue positions.
• <b>Duration Display:</b> Fixed InnerTube duration formatting (e.g. <code>0:213</code>).

<b>{EmojiTag.BOLT} ᴘᴇʀꜰᴏʀᴍᴀɴᴄᴇ:</b>
• <b>Faster Playback Latency:</b> Prioritized InnerTube stream resolution over yt-dlp (~3.2s → ~800ms).
• <b>Connection Pooling:</b> Reused persistent HTTP/2 <code>httpx</code> and <code>aiohttp</code> sessions across requests.
• <b>Background Tasks:</b> Offloaded message deletions to background tasks.

<b>{EmojiTag.TOOLS} ᴏᴛʜᴇʀ ᴄʜᴀɴɢᴇs:</b>
• Added <code>httpx[http2]</code> to dependencies and removed deprecated <code>mode</code> parameter from <code>/info</code>.

<b>{EmojiTag.INFO} sᴜᴍᴍᴀʀʏ:</b>
<blockquote>Since commit <code>2ce88f5</code>, the bot gained a smart YouTube Music autoplay system, direct stream URL support, and Telegram custom emojis. Latency was drastically cut via InnerTube priority and HTTP/2 pooling, alongside key bug fixes for Telegram markup and skip permission checks.</blockquote>

{EmojiTag.REPO} <b>ɢɪᴛʜᴜʙ:</b> <a href="https://github.com/nub-coders/nub-music-bot">nub-coders/nub-music-bot</a>
{EmojiTag.USER} <b>ʙᴏᴛ:</b> @nub_MusicBot"""


async def send_message(target: str, token: str):
    print(f"Connecting bot client to send update to '{target}'...")
    app = Client(
        "update_sender",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=token,
        in_memory=True,
    )

    async with app:
        me = await app.get_me()
        print(f"Logged in as bot: @{me.username} ({me.id})")

        # Try resolving target or prepending @ if needed
        chat_target = target
        if isinstance(target, str) and not target.startswith("@") and not target.lstrip("-").isdigit():
            chat_target = f"@{target}"

        print(f"Sending formatted message with custom emojis to {chat_target}...")
        sent = await app.send_message(
            chat_id=chat_target,
            text=MESSAGE_TEMPLATE,
            link_preview_options=None,
        )
        print(f"✅ Successfully sent message to {chat_target} (Message ID: {sent.id})")


def main():
    parser = argparse.ArgumentParser(description="Send release notes with custom emojis to Telegram user/chat.")
    parser.add_argument("--to", "-t", default="just_a_dev", help="Target username or chat ID (default: just_a_dev)")
    parser.add_argument("--bot-token", "-b", default=None, help="Telegram Bot Token (default: from BOT_TOKEN in .env)")

    args = parser.parse_args()

    token = args.bot_token or os.getenv("BOT_TOKEN") or CONFIG_BOT_TOKEN
    if not token:
        print("❌ Error: BOT_TOKEN is not set.")
        sys.exit(1)

    try:
        asyncio.run(send_message(args.to, token))
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
