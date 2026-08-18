"""plugins/meme.py — /kang sticker stealing and /mmf meme text."""

from plugins._common import *  # noqa: F401,F403


@Client.on_message(filters.command("kang"))
async def kang(client, message):
    client = clients['session']
    user = message.from_user
    if not user:
       return await message.reply_text(Messages.USE_COMMAND_AS_USER, link_preview_options=None)
    replied = message.reply_to_message
    if not replied or not replied.media:
        return await message.reply_text(Messages.REPLY_TO_MEDIA, link_preview_options=None)

    Nub = await message.reply_text(Messages.STICKER_LONG, link_preview_options=None)
    media_ = None
    emoji_ = None
    is_anim = False
    is_video = False
    resize = False
    ff_vid = False
    if replied.photo:
        resize = True
    elif replied.document and "image" in replied.document.mime_type:
        resize = True
        replied.document.file_name
    elif replied.document and "tgsticker" in replied.document.mime_type:
        is_anim = True
        replied.document.file_name
    elif replied.document and "video" in replied.document.mime_type:
        resize = True
        is_video = True
        ff_vid = True
    elif replied.animation:
        resize = True
        is_video = True
        ff_vid = True
    elif replied.video:
        resize = True
        is_video = True
        ff_vid = True
    elif replied.sticker:
        if not replied.sticker.file_name:
            await Nub.edit(Messages.STICKER_NO_NAME)
            return
        emoji_ = replied.sticker.emoji
        is_anim = replied.sticker.is_animated
        is_video = replied.sticker.is_video
        if not (
            replied.sticker.file_name.endswith(".tgs")
            or replied.sticker.file_name.endswith(".webm")
        ):
            resize = True
            ff_vid = True
    else:
        await Nub.edit(Messages.UNSUPPORTED_FILE)
        return
    media_ = await client.download_media(replied, file_name=f"{ggg}/user_{client.me.id}/")
    if media_:
        args = get_arg(message)
        pack = 1
        if len(args) == 2:
            emoji_, pack = args
        elif len(args) == 1:
            if args[0].isnumeric():
                pack = int(args[0])
            else:
                emoji_ = args[0]

        if emoji_:
            def is_unicode_emoji(s: str) -> bool:
                if not s:
                    return False
                emoji_re = re.compile(
                    "["
                    "\U0001F300-\U0001F6FF"
                    "\U0001F700-\U0001F77F"
                    "\U0001F780-\U0001F7FF"
                    "\U0001F800-\U0001F8FF"
                    "\U0001F900-\U0001F9FF"
                    "\U0001FA00-\U0001FA6F"
                    "\U0001FA70-\U0001FAFF"
                    "\U00002702-\U000027B0"
                    "\U000024C2-\U0001F251"
                    "]+",
                    flags=re.UNICODE,
                )
                return bool(emoji_re.fullmatch(s) or emoji_re.search(s))

            valid = False
            # normalize
            e = str(emoji_).strip()

            # If user provided a named constant (e.g., PLAY, MUSIC_NOTE)
            if hasattr(Emoji, e):
                emoji_ = getattr(Emoji, e)
                valid = True

            # If it's purely numeric, treat as custom emoji id
            if not valid and e.isdigit():
                try:
                    emoji_ = int(e)
                    valid = True
                except Exception:
                    valid = False

            # If it's a unicode emoji (one or more glyphs), accept as-is
            if not valid and is_unicode_emoji(e):
                emoji_ = e
                valid = True

            # As a last resort, check if it matches any Emoji constant values
            if not valid:
                try:
                    for name in dir(Emoji):
                        if name.startswith("_"):
                            continue
                        val = getattr(Emoji, name)
                        if str(val) == e:
                            emoji_ = val
                            valid = True
                            break
                except Exception:
                    valid = False

            if not valid:
                emoji_ = None
        if not emoji_:
            emoji_ = "✨"

        u_name = user.username
        u_name = "@" + u_name if u_name else user.first_name or user.id
        packname = f"Sticker_u{user.id}_v{pack}"
        custom_packnick = f"{u_name} Sticker Pack"
        packnick = f"{custom_packnick} Vol.{pack}"
        cmd = "/newpack"
        if resize:
            media_ = await resize_media(media_, is_video, ff_vid)
        if is_anim:
            packname += "_animated"
            packnick += " (Animated)"
            cmd = "/newanimated"
        if is_video:
            packname += "_video"
            packnick += " (Video)"
            cmd = "/newvideo"
        exist = False
        while True:
            try:
                exist = await client.invoke(
                    GetStickerSet(
                        stickerset=InputStickerSetShortName(short_name=packname), hash=0
                    )
                )
            except StickersetInvalid:
                exist = False
                break
            limit = 50 if (is_video or is_anim) else 120
            if exist.set.count >= limit:
                pack += 1
                packname = f"a{user.id}_by_userge_{pack}"
                packnick = f"{custom_packnick} Vol.{pack}"
                if is_anim:
                    packname += f"_anim{pack}"
                    packnick += f" (Animated){pack}"
                if is_video:
                    packname += f"_video{pack}"
                    packnick += f" (Video){pack}"
                await Nub.edit(
                    f"`Create a New Sticker Pack {pack} Because the Sticker Pack is Full`"
                )
                continue
            break
        if exist is not False:
            try:
                await client.send_message("stickers", "/addsticker", link_preview_options=None)
            except YouBlockedUser:
                await client.unblock_user("stickers")
                await client.send_message("stickers", "/addsticker", link_preview_options=None)
            except Exception as e:
                logger.error(f"[kang] Sticker pack step failed: {e}")
                return await Nub.edit("**ERROR:** Failed to create the sticker. Please try again.")
            await asyncio.sleep(2)
            await client.send_message("stickers", packname, link_preview_options=None)
            await asyncio.sleep(2)
            limit = "50" if is_anim else "120"
            while limit in await get_response(message, client):
                pack += 1
                packname = f"a{user.id}_by_{user.username}_{pack}"
                packnick = f"{custom_packnick} vol.{pack}"
                if is_anim:
                    packname += "_anim"
                    packnick += " (Animated)"
                if is_video:
                    packname += "_video"
                    packnick += " (Video)"
                    await Nub.edit(
                    f"`Creating a New Sticker Pack {pack} Because the Sticker Pack is Full`"
                )
                await client.send_message("stickers", packname, link_preview_options=None)
                await asyncio.sleep(2)
                if await get_response(message, client) == "Invalid pack selected.":
                    await client.send_message("stickers", cmd, link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_message("stickers", packnick, link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_document("stickers", media_)
                    await asyncio.sleep(2)
                    await client.send_message("Stickers", emoji_, link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_message("Stickers", "/publish", link_preview_options=None)
                    await asyncio.sleep(2)
                    if is_anim:
                        await client.send_message(
                            "Stickers", f"<{packnick}>", parse_mode=enums.ParseMode.MARKDOWN,
                        link_preview_options=None)
                        await asyncio.sleep(2)
                    await client.send_message("Stickers", "/skip", link_preview_options=None)
                    await asyncio.sleep(2)
                    await client.send_message("Stickers", packname, link_preview_options=None)
                    await asyncio.sleep(2)
                    await Nub.edit(
                        f"**Sticker Added Successfully!**\n 🔥 **[CLICK HERE](https://t.me/addstickers/{packname})** 🔥\n**To Use Stickers**"
                    )
            await client.send_document("stickers", media_)
            await asyncio.sleep(2)
            if (
                await get_response(message, client)
                == "Sorry, the file type is invalid."
            ):
                await Nub.edit(
                    "**Failed to Add Sticker, Use @Stickers Bot to Add Your Sticker.**"
                )
                return
            await client.send_message("Stickers", emoji_, link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", "/done", link_preview_options=None)
        else:
            await Nub.edit(Messages.CREATING_STICKER_PACK)
            try:
                await client.send_message("Stickers", cmd, link_preview_options=None)
            except YouBlockedUser:
                await client.unblock_user("stickers")
                await client.send_message("stickers", "/addsticker", link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", packnick, link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_document("stickers", media_)
            await asyncio.sleep(2)
            if (
                await get_response(message, client)
                == "Sorry, the file type is invalid."
            ):
                await Nub.edit(
                    "**Failed to Add Sticker, Use @Stickers Bot to Add Your Sticker.**"
                )
                return
            await client.send_message("Stickers", emoji_, link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", "/publish", link_preview_options=None)
            await asyncio.sleep(2)
            if is_anim:
                await client.send_message("Stickers", f"<{packnick}>", link_preview_options=None)
                await asyncio.sleep(2)
            await client.send_message("Stickers", "/skip", link_preview_options=None)
            await asyncio.sleep(2)
            await client.send_message("Stickers", packname, link_preview_options=None)
            await asyncio.sleep(2)
        await Nub.edit(
            f"**Sticker Added Successfully!**\n 🔥 **[CLICK HERE](https://t.me/addstickers/{packname})** 🔥\n**To Use Stickers**"
        )
        if os.path.exists(str(media_)):
            os.remove(media_)


async def get_response(message, client):
    return [x async for x in client.get_chat_history("Stickers", limit=1)][0].text


@Client.on_message(filters.command("mmf"))
async def memify(client, message):
    if not message.reply_to_message or not message.reply_to_message.media:
        return await message.reply_text(Messages.REPLY_TO_PHOTO_OR_STICKER, link_preview_options=None)
    text = get_arg(message).strip()
    if not text:
        return await message.reply_text(Messages.MMF_USAGE, link_preview_options=None)
    reply_message = message.reply_to_message
    Nub = await message.reply_text(Messages.PROCESSING, link_preview_options=None)
    file = await client.download_media(reply_message)
    if not file:
        return await Nub.edit(Messages.MMF_DOWNLOAD_FAILED)
    try:
        meme = await add_text_img(file, text)
        await asyncio.gather(
            Nub.delete(),
            client.send_sticker(
                message.chat.id,
                sticker=meme,
                reply_to_message_id=reply_message.id,
            ),
        )
        if os.path.exists(meme):
            os.remove(meme)
    finally:
        if os.path.exists(file):
            os.remove(file)
    try:
        await message.delete()
    except Exception:
        pass
