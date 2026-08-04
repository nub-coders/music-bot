"""plugins/queue_cmds.py — /queue view and /tagall /cancel /del group utilities."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command("queue"))
async def queue_command(client, message):
    chat_id = message.chat.id
    queue_list = state.queues.get(chat_id, [])
    items = queue_list[:20]
    if not items:
        return await message.reply(Messages.QUEUE_EMPTY, link_preview_options=None)

    # Build styled queue text
    text_lines = ["🎵 | ǫᴜᴇᴜᴇ (ᴍᴀx 20)\n"]
    for idx, item in enumerate(items, 1):
        title = item.get("title", "Unknown")
        duration = item.get("duration", "-")
        text_lines.append(f"{idx}. {title}  [{duration}]")

    # Create dark gradient-style image
    width, height = 900, 650
    img = Image.new("RGB", (width, height), (15, 15, 30))  # deep dark indigo
    draw = ImageDraw.Draw(img)
    # Draw a subtle accent bar on the left
    for x in range(8):
        _opacity = max(0, 255 - x * 30)
        draw.rectangle([(x, 0), (x, height)], fill=(138, 43, 226))
    # Font
    try:
        font_title = ImageFont.truetype("Poppins-Bold.ttf", 36)
        font_body  = ImageFont.truetype("Poppins-Regular.ttf", 28)
    except Exception:
        font_title = ImageFont.load_default()
        font_body  = font_title
    # Title
    draw.text((30, 30), text_lines[0].strip(), fill=(200, 150, 255), font=font_title)
    # Body items
    y = 90
    for line in text_lines[1:]:
        draw.text((30, y), line, fill=(230, 230, 255), font=font_body)
        y += 40

    # Save to bytes
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    styled_caption = (
        f"<u><b>{EmojiTag.MUSIC_NOTE} | ᴄᴜʀʀᴇɴᴛ ǫᴜᴇᴜᴇ</b></u>\n"
        "<blockquote expandable>\n"
        + "\n".join(
            f"<b>{idx}.</b> {item.get('title','Unknown')}  <code>[{item.get('duration','-')}]</code>"
            for idx, item in enumerate(items, 1)
        )
        + "\n</blockquote>"
    )
    await message.reply_photo(photo=buf, caption=styled_caption)


@Client.on_message(filters.command("shuffle"))
@admin_only()
async def shuffle_queue(client, message):
    chat_id = message.chat.id
    async with state.lock(chat_id):
        q = state.queues.get(chat_id)
        if not q or len(q) < 2:
            return await message.reply(Messages.NOTHING_TO_SHUFFLE, link_preview_options=None)
        random.shuffle(q)
        n = len(q)
    await message.reply(Messages.QUEUE_SHUFFLED.format(n), link_preview_options=None)


@Client.on_message(filters.command("tagall") & filters.group)
@admin_only()
async def mentionall(client, message):
    await message.delete()
    chat_id = message.chat.id
    direp = message.reply_to_message
    args = get_arg(message)

    # If no message or reply provided, use random message from TAGALL
    if not direp and not args:
        args = random.choice(TAGALL)

    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if chat_id not in spam_chats:
            break
        usrnum += 1
        usrtxt += f"{usr.user.mention()}, "
        if usrnum == 5:
            if args:
                txt = f"<blockquote>{args}\n\n{usrtxt}</blockquote>"
                await client.send_message(chat_id, txt, link_preview_options=None)
            elif direp:
                await direp.reply(f"<blockquote>{usrtxt}</blockquote>", link_preview_options=None)
            await asyncio.sleep(5)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except Exception:
        pass


@Client.on_message(filters.command("cancel") & filters.group)
@admin_only()
async def cancel_spam(client, message):
    if message.chat.id not in spam_chats:
        return await message.reply(Messages.NO_TAGALL, link_preview_options=None)
    else:
        try:
            spam_chats.remove(message.chat.id)
        except Exception:
            pass
        return await message.reply(Messages.DISMISS_MENTION, link_preview_options=None)


@Client.on_message(filters.command("del") & filters.group)
@admin_only()
async def delete_message_handler(client, message):
    # Check if the message is a reply
    if message.reply_to_message:
        try:
            # Delete the replied message
            await message.reply_to_message.delete()
            # Optionally, delete the command message as well
            await message.delete()
        except MessageDeleteForbidden:
              pass
        except Exception as e:
            logger.error(f"[del] Failed to delete message: {e}")
            await message.reply(Messages.ERROR_DEL_MSG, link_preview_options=None)
    else:
        await message.reply(Messages.REPLY_TO_DEL, link_preview_options=None)
