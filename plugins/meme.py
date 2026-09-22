"""plugins/meme.py — /kang sticker stealing and /mmf meme text."""

from pyrogram.raw.functions.stickers import CreateStickerSet, AddStickerToSet
from pyrogram.raw.types import InputDocument, InputStickerSetItem
from plugins._common import *  # noqa: F401,F403


def _sticker_added_card(packname: str) -> str:
    """Success card for a kanged sticker (replaces the old markdown blob)."""
    return (
        rich_heading(f"{EmojiTag.SUCCESS} sᴛɪᴄᴋᴇʀ ᴀᴅᴅᴇᴅ", 1)
        + rich_kv_table([
            (f"{EmojiTag.KANG} ᴘᴀᴄᴋ", rich_code(packname)),
            (
                f"{EmojiTag.LINK} ɪɴsᴛᴀʟʟ",
                f'<a href="https://t.me/addstickers/{packname}"><b>ᴄʟɪᴄᴋ ʜᴇʀᴇ</b></a>',
            ),
        ])
        + rich_note(f"{EmojiTag.INFO} <i>ᴀᴅᴅ ᴛʜᴇ ᴘᴀᴄᴋ ᴛᴏ sᴛᴀʀᴛ ᴜsɪɴɢ ʏᴏᴜʀ sᴛɪᴄᴋᴇʀs.</i>")
    )


_STICKER_FAILED = (
    f"{EmojiTag.ERROR} <b>꩖ᴀɪʟᴇᴅ ᴛᴏ ᴀᴅᴅ sᴛɪᴄᴋᴇʀ.</b> "
    "ᴜsᴇ ᴛʜᴇ ᴘᴀᴄᴋ ʟɪɴᴋ ᴛᴏ ᴀᴅᴅ ɪᴛ ᴍᴀɴᴜᴀʟʟʏ."
)


@Client.on_message(filters.command("kang"))
async def kang(client, message):
    user = message.from_user
    if not user:
        return await rich_reply(message, rich_note(Messages.USE_COMMAND_AS_USER), ephemeral=True)
    replied = message.reply_to_message
    if not replied or not replied.media:
        return await rich_reply(message, rich_note(Messages.REPLY_TO_MEDIA), ephemeral=True)

    Nub = await rich_reply(message, rich_note(Messages.STICKER_LONG))
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
    elif replied.document and "tgsticker" in replied.document.mime_type:
        is_anim = True
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
            await rich_edit(Nub, rich_note(Messages.STICKER_NO_NAME))
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
        await rich_edit(Nub, rich_note(Messages.UNSUPPORTED_FILE))
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
        if resize:
            media_ = await resize_media(media_, is_video, ff_vid)
        if is_anim:
            packname += "_animated"
            packnick += " (Animated)"
        if is_video:
            packname += "_video"
            packnick += " (Video)"
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
                packname = f"Sticker_u{user.id}_v{pack}"
                packnick = f"{custom_packnick} Vol.{pack}"
                if is_anim:
                    packname += "_animated"
                    packnick += " (Animated)"
                if is_video:
                    packname += "_video"
                    packnick += " (Video)"
                await rich_edit(
                    Nub,
                    rich_note(f"{EmojiTag.INFO} Creating a new sticker pack {rich_code(pack)} — the previous pack is full."),
                )
                continue
            break

    # ── Add the sticker via direct MTProto RPCs on the user session ──
    try:
        emoji_str = str(emoji_) if emoji_ is not None else "✨"
        if isinstance(emoji_, int):
            logger.info(
                "[kang] Custom emoji id %s converted to string for MTProto layer.",
                emoji_,
            )
        sticker_doc = await client.save_file(media_)
        sticker = InputStickerSetItem(
            document=InputDocument(
                id=sticker_doc.id,
                access_hash=getattr(sticker_doc, "access_hash", 0),
                file_reference=getattr(sticker_doc, "file_reference", b"") or b"",
            ),
            emoji=emoji_str,
        )
        if exist:
            await client.invoke(
                AddStickerToSet(
                    stickerset=InputStickerSetShortName(short_name=packname),
                    sticker=sticker,
                )
            )
        else:
            await rich_edit(Nub, rich_note(Messages.CREATING_STICKER_PACK))
            await client.invoke(
                CreateStickerSet(
                    user_id=client.me.raw,
                    title=packnick,
                    short_name=packname,
                    stickers=[sticker],
                    masks=False,
                    emojis=False,
                    text_color=False,
                )
            )
        await rich_edit(Nub, _sticker_added_card(packname))
    except Exception as e:
        logger.error(f"[kang] Failed to add sticker: {e}")
        await rich_edit(Nub, rich_note(_STICKER_FAILED))
        return

    if os.path.exists(str(media_)):
        os.remove(media_)


@Client.on_message(filters.command("mmf"))
async def memify(client, message):
    if not message.reply_to_message or not message.reply_to_message.media:
        return await rich_reply(message, rich_note(Messages.REPLY_TO_PHOTO_OR_STICKER), ephemeral=True, client=client)
    text = get_arg(message).strip()
    if not text:
        return await rich_reply(message, rich_note(Messages.MMF_USAGE), ephemeral=True, client=client)
    reply_message = message.reply_to_message
    # Streaming draft for the render: the real output is a sticker, so the draft
    # is discarded rather than persisted (it expires on its own).
    draft = RichDraft(client, message.chat.id, message_thread_id=getattr(message, "message_thread_id", None))
    await draft.update(rich_note(Messages.PROCESSING))
    file = await client.download_media(reply_message)
    if not file:
        draft.discard()
        return await rich_reply(message, rich_note(Messages.MMF_DOWNLOAD_FAILED), ephemeral=True, client=client)
    meme = None
    try:
        await draft.update(
            rich_heading(f"{EmojiTag.KANG} ʀᴇɴᴅᴇʀɪɴɢ ᴍᴇᴍᴇ", 2)
            + rich_kv_table([(f"{EmojiTag.LOADING} sᴛᴇᴘ", "ᴅʀᴀᴡɪɴɢ ᴛᴇxᴛ ᴏᴠᴇʀʟᴀʏ")])
        )
        meme = await add_text_img(file, text)
        draft.discard()
        await client.send_sticker(
            message.chat.id,
            sticker=meme,
            reply_to_message_id=reply_message.id,
        )
    except Exception as e:
        logger.error(f"[memify] Error: {e}")
        draft.discard()
        try:
            await rich_reply(
                message,
                rich_note(f"{EmojiTag.ERROR} <b>Failed to create meme:</b> {rich_code(e)}"),
                ephemeral=True,
                client=client,
            )
        except Exception as notify_error:
            logger.debug(f"[memify] Failure notice could not be sent in chat {message.chat.id}: {notify_error}")
    finally:
        # Both the download and the rendered meme must go even when
        # send_sticker raises (file too large, forbidden, flood wait) --
        # previously the meme cleanup sat in the success path only and leaked.
        if meme and os.path.exists(meme):
            try:
                os.remove(meme)
            except OSError as e:
                logger.debug(f"[memify] Could not remove rendered meme {meme}: {e}")
        if os.path.exists(file):
            try:
                os.remove(file)
            except OSError as e:
                logger.debug(f"[memify] Could not remove downloaded source {file}: {e}")
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"[memify] Could not delete command message {message.id} in chat {message.chat.id}: {e}")
