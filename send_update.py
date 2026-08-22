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


MESSAGE_TEMPLATE = f"""<u><b>{EmojiTag.ROCKET} | ʀɪᴄʜ ᴜɪ ᴜᴘᴅᴀᴛᴇ</b></u>

<b>{EmojiTag.SPARKLE_STAR} ᴡʜᴀᴛ's ɴᴇᴡ:</b>
• Stats, queues and settings now render as clean <b>tables</b>.
• Long help pages fold into <b>collapsible sections</b>.
• Inline buttons are <b>colour-styled</b>, and confirmations reply <b>privately</b>.
• Fixed <b>premium custom emoji</b> showing up as plain emoji.

<blockquote>Same commands, cleaner output — a full interface refresh built on Bot API 10.2.</blockquote>

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
