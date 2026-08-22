"""plugins/queue_cmds.py — /queue view and /tagall /cancel /del group utilities."""

from plugins._common import *  # noqa: F401,F403


def _render_queue_image_sync(display_items, header_text="CURRENT QUEUE (MAX 20)"):
    from io import BytesIO
    width, height = 900, 650
    img = Image.new("RGB", (width, height), (15, 15, 30))  # deep dark indigo
    draw = ImageDraw.Draw(img)
    # Draw a subtle accent bar on the left
    for x in range(8):
        draw.rectangle([(x, 0), (x, height)], fill=(138, 43, 226))
    # Font
    try:
        font_title = ImageFont.truetype("Poppins-Bold.ttf", 36)
        font_body  = ImageFont.truetype("Poppins-Regular.ttf", 26)
    except Exception:
        font_title = ImageFont.load_default()
        font_body  = font_title
    # Title
    draw.text((35, 30), header_text, fill=(200, 150, 255), font=font_title)
    # Body items
    y = 85
    for idx, title, duration in display_items:
        # Truncate title on image to fit width nicely
        img_title = (title[:42] + "…") if len(title) > 45 else title
        draw.text((35, y), f"{idx}. {img_title}  [{duration}]", fill=(230, 230, 255), font=font_body)
        y += 36

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@Client.on_message(filters.command(["queue", "cqueue"]))
async def queue_command(client, message):
    chat_id = message.chat.id
    is_channel = message.command[0].lower() == "cqueue"
    if is_channel or (not state.queues.get(chat_id)):
        try:
            linked = (await client.get_chat(chat_id)).linked_chat
            if linked and (is_channel or state.queues.get(linked.id)):
                chat_id = linked.id
        except Exception:
            pass
    queue_list = state.queues.get(chat_id, [])
    items = queue_list[:20]
    if not items:
        return await rich_reply(message, rich_note(Messages.QUEUE_EMPTY), ephemeral=True, client=client)

    # Build styled queue items (read-only, does not mutate live QueueEntry objects)
    header_text = "CURRENT QUEUE (MAX 20)"
    display_items = []
    for idx, item in enumerate(items, 1):
        raw_title = item.get("title") or "Unknown"
        dur = item.get("duration")
        yt_task = item.get("_yt_task")
        if yt_task and yt_task.done() and not yt_task.cancelled() and not yt_task.exception():
            try:
                res = yt_task.result()
                if res and len(res) >= 2:
                    if res[0] and res[0] != "Error":
                        raw_title = res[0]
                    if res[1] and res[1] != "N/A":
                        dur = res[1]
            except Exception:
                pass

        title = trim_title(raw_title) if raw_title else "Unknown"
        duration = str(dur) if dur and str(dur).lower() not in ("none", "n/a", "") else "-"
        display_items.append((idx, title, duration))

    # Render image in worker thread to avoid blocking event loop
    buf = await asyncio.to_thread(_render_queue_image_sync, display_items, header_text)

    # Caption-bound UI: the queue ships as a rendered PNG and captions have no
    # `rich_message` parameter, so the table is flattened with rich_caption()
    # rather than duplicating a second layout for this one view.
    styled_caption = rich_caption(
        rich_heading(f"{EmojiTag.MUSIC_NOTE} ᴄᴜʀʀᴇɴᴛ ǫᴜᴇᴜᴇ", 1)
        + rich_table(
            ["#", "ᴛʀᴀᴄᴋ", "ʟᴇɴɢᴛʜ"],
            [
                (f"<b>{idx}</b>", rich_esc(title), rich_code(duration))
                for idx, title, duration in display_items
            ],
        )
    )
    await message.reply_photo(photo=buf, caption=styled_caption)



@Client.on_message(filters.command(["shuffle", "cshuffle"]))
@admin_only()
async def shuffle_queue(client, message):
    chat_id = message.chat.id
    is_channel = message.command[0].lower() == "cshuffle"
    if is_channel or (not state.queues.get(chat_id)):
        try:
            linked = (await client.get_chat(chat_id)).linked_chat
            if linked and (is_channel or state.queues.get(linked.id)):
                chat_id = linked.id
        except Exception:
            pass
    async with state.lock(chat_id):
        q = state.queues.get(chat_id)
        if not q or len(q) < 2:
            return await rich_reply(message, rich_note(Messages.NOTHING_TO_SHUFFLE), ephemeral=True, client=client)
        random.shuffle(q)
        n = len(q)
    # Public: shuffling changes playback order for the whole chat.
    await rich_reply(message, rich_note(Messages.QUEUE_SHUFFLED.format(n)), client=client)


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
                txt = f"<blockquote>{EmojiTag.BROADCAST} <b>{args}</b>\n\n{usrtxt}</blockquote>"
                await rich_send(client, chat_id, txt)
            elif direp:
                await direp.reply(f"<blockquote>{EmojiTag.BROADCAST} {usrtxt}</blockquote>", link_preview_options=None)
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
        return await rich_reply(message, rich_note(Messages.NO_TAGALL), ephemeral=True, client=client)
    else:
        try:
            spam_chats.remove(message.chat.id)
        except Exception:
            pass
        return await rich_reply(message, rich_note(Messages.DISMISS_MENTION), ephemeral=True, client=client)


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
            await rich_reply(message, rich_note(Messages.ERROR_DEL_MSG), ephemeral=True, client=client)
    else:
        await rich_reply(message, rich_note(Messages.REPLY_TO_DEL), ephemeral=True, client=client)
