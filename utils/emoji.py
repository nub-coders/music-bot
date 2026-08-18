"""
Premium Custom Emoji IDs
Curated from Telegram emoji packs:
  - NewsEmoji (https://t.me/addemoji/NewsEmoji)
  - TgAndroidIcons (https://t.me/addemoji/TgAndroidIcons)
  - EmojiStatus (https://t.me/addemoji/EmojiStatus)
  - DMJUnigramAnimationEmoji

Usage in messages:
    from pyrogram import enums
    from pyrogram.types import MessageEntity

    entity = MessageEntity(
        type=enums.MessageEntityType.CUSTOM_EMOJI,
        offset=0,
        length=1,
        custom_emoji_id=Emoji.MUSIC_NOTE
    )
    await bot.send_message(chat_id, "⬜ Now Playing...", entities=[entity])

Usage in buttons (Kurigram required):
    InlineKeyboardButton("Play", callback_data="play", icon_custom_emoji_id=Emoji.PLAY)
"""


class Emoji:
    # ── Playback / Music ──────────────────────────────────────────────────────
    MUSIC_NOTE     = 5891249688933305846   # 🎵  TgAndroidIcons
    MUSIC_NOTES    = 5915480455603295660   # 🎶  TgAndroidIcons
    HEADPHONES     = 6007938409857815902   # 🎧  TgAndroidIcons
    MIC            = 5224736245665511429   # 🎙  NewsEmoji
    BROADCAST      = 5424818078833715060   # 📢  NewsEmoji
    PLAY           = 5348125953090403204   # ▶️  NewsEmoji
    SKIP           = 5875506366050734240   # ➡️  TgAndroidIcons
    RESUME         = 5348125953090403204   # ▶️  NewsEmoji
    PAUSE          = 5359543311897998264   # ⏸  NewsEmoji
    STOP           = 5260293700088511294   # 🚫  NewsEmoji
    LOOP           = 5375338737028841420   # 🔄  NewsEmoji
    BOLT           = 5224607267797606837   # ⚡️  NewsEmoji

    # ── Status / Info ─────────────────────────────────────────────────────────
    NOW_PLAYING    = 5890831539507302154   # 🎵  TgAndroidIcons
    QUEUE_ICON     = 5877316724830768997   # 🗃   TgAndroidIcons
    LOADING        = 5375338737028841420   # 🔄  NewsEmoji
    SETTINGS       = 5341715473882955310   # ⚙️  NewsEmoji
    INFO           = 5323442290708985472   # ℹ️  NewsEmoji
    STATS          = 5231200819986047254   # 📊  NewsEmoji
    PING           = 5224607267797606837   # ⚡️  NewsEmoji

    # ── Success / Error ───────────────────────────────────────────────────────
    SUCCESS        = 5206607081334906820   # ✅  NewsEmoji
    ERROR          = 5210952531676504517   # ❌  NewsEmoji
    WARNING        = 5447644880824181073   # ⚠️  NewsEmoji
    BLOCKED        = 5260293700088511294   # 🚫  NewsEmoji
    LOCK           = 5296369303661067030   # 🔒  NewsEmoji
    UNLOCK         = 6034962180875490251   # 🔓  TgAndroidIcons
    SHIELD         = 5926783847453692661   # 🛡   TgAndroidIcons

    # ── User / Admin ──────────────────────────────────────────────────────────
    CROWN          = 5807868868886009920   # 👑  EmojiStatus
    DIAMOND        = 5963312935148195483   # 💎  TgAndroidIcons
    STAR           = 5438496463044752972   # ⭐  NewsEmoji
    USER           = 5771887475421090729   # 👤  TgAndroidIcons
    USERS          = 5942877472163892475   # 👥  TgAndroidIcons
    KEY            = 6005570495603282482   # 🔑  TgAndroidIcons
    FIRE           = 5424972470023104089   # 🔥  NewsEmoji
    SPARKLE_STAR   = 5438496463044752972   # ⭐  NewsEmoji

    # ── Navigation / UI ───────────────────────────────────────────────────────
    BACK           = 5877629862306385808   # ◀️  TgAndroidIcons
    CLOSE          = 5240241223632954241   # ❌  NewsEmoji
    HOME           = 5967822972931542886   # 🏠  TgAndroidIcons
    REFRESH        = 5375338737028841420   # 🔄  NewsEmoji
    REPO           = 5271604874419647061   # 🔗  NewsEmoji
    NEXT           = 5877468380125990242   # ➡️  TgAndroidIcons
    ADD            = 5397916757333654639   # ➕  NewsEmoji
    PIN            = 5397782960512444700   # 📌  NewsEmoji

    # ── Message types ─────────────────────────────────────────────────────────
    CHAT           = 5443038326535759644   # 💬  NewsEmoji
    SEND           = 5253742260054409879   # ✉️  NewsEmoji
    ROCKET         = 5857290546459973028   # 🚀  DMJUnigramAnimationEmoji
    GLOBE          = 5447410659077661506   # 🌐  NewsEmoji
    LINK           = 5271604874419647061   # 🔗  NewsEmoji
    TOOLS          = 5988023995125993550   # 🛠   TgAndroidIcons
    KANG           = 5814690801665446789   # 🎨  TgAndroidIcons
    SUDO           = 5807868868886009920   # 👑  EmojiStatus
    OWNER          = 5341715473882955310   # ⚙️  NewsEmoji
    BROADCAST_BTN  = 5424818078833715060   # 📢  NewsEmoji
    AUTH_ICON      = 5296369303661067030   # 🔒  NewsEmoji
    BLOCKLIST_ICON = 5260293700088511294   # 🚫  NewsEmoji
    HELP           = 5323442290708985472   # ℹ️  NewsEmoji

    # ── Digits & Tens ─────────────────────────────────────────────────────────
    DIGITS = {
        "1": 5794182096603847292,           # 1️⃣
        "2": 5794303034292968945,           # 2️⃣
        "3": 5794031944547178894,           # 3️⃣
        "4": 5793901252987330401,           # 4️⃣
        "5": 5794066823976592976,           # 5️⃣
        "6": 5794235255414069703,           # 6️⃣
        "7": 5794030595927448202,           # 7️⃣
        "8": 5794426162415409242,           # 8️⃣
        "9": 5793905801357695657,           # 9️⃣
    }

    TENS = {
        "10": 5794310013614824017,          # 10
        "20": 5794342041185949794,          # 20
        "30": 5794170049220581625,          # 30
        "40": 5794071015864671326,          # 40
        "50": 5794348440687221181,          # 50
        "60": 5794246418034072201,          # 60
        "70": 5793932490284472550,          # 70
        "80": 5794335744763894508,          # 80
        "90": 5794442693744531795,          # 90
    }



class EmojiTag:
    """Pre-formatted HTML custom emoji tags for messages."""
    MUSIC_NOTE     = f'<emoji id="{Emoji.MUSIC_NOTE}">🎵</emoji>'
    MUSIC_NOTES    = f'<emoji id="{Emoji.MUSIC_NOTES}">🎶</emoji>'
    HEADPHONES     = f'<emoji id="{Emoji.HEADPHONES}">🎧</emoji>'
    MIC            = f'<emoji id="{Emoji.MIC}">🎤</emoji>'
    BROADCAST      = f'<emoji id="{Emoji.BROADCAST}">📢</emoji>'
    PLAY           = f'<emoji id="{Emoji.PLAY}">🎞</emoji>'
    SKIP           = f'<emoji id="{Emoji.SKIP}">➡️</emoji>'
    RESUME         = f'<emoji id="{Emoji.RESUME}">🎞</emoji>'
    PAUSE          = f'<emoji id="{Emoji.PAUSE}">🔇</emoji>'
    STOP           = f'<emoji id="{Emoji.STOP}">🚫</emoji>'
    LOOP           = f'<emoji id="{Emoji.LOOP}">🔄</emoji>'
    BOLT           = f'<emoji id="{Emoji.BOLT}">⚡</emoji>'

    NOW_PLAYING    = f'<emoji id="{Emoji.NOW_PLAYING}">🎵</emoji>'
    QUEUE_ICON     = f'<emoji id="{Emoji.QUEUE_ICON}">🗃</emoji>'
    LOADING        = f'<emoji id="{Emoji.LOADING}">⚙️</emoji>'
    SETTINGS       = f'<emoji id="{Emoji.SETTINGS}">⚙️</emoji>'
    INFO           = f'<emoji id="{Emoji.INFO}">ℹ️</emoji>'
    STATS          = f'<emoji id="{Emoji.STATS}">📊</emoji>'
    PING           = f'<emoji id="{Emoji.PING}">⚡</emoji>'

    SUCCESS        = f'<emoji id="{Emoji.SUCCESS}">✅</emoji>'
    ERROR          = f'<emoji id="{Emoji.ERROR}">❌</emoji>'
    WARNING        = f'<emoji id="{Emoji.WARNING}">⚠️</emoji>'
    BLOCKED        = f'<emoji id="{Emoji.BLOCKED}">🚫</emoji>'
    LOCK           = f'<emoji id="{Emoji.LOCK}">🔐</emoji>'
    UNLOCK         = f'<emoji id="{Emoji.UNLOCK}">🔓</emoji>'
    SHIELD         = f'<emoji id="{Emoji.SHIELD}">🛡</emoji>'

    CROWN          = f'<emoji id="{Emoji.CROWN}">👑</emoji>'
    DIAMOND        = f'<emoji id="{Emoji.DIAMOND}">💎</emoji>'
    STAR           = f'<emoji id="{Emoji.STAR}">⭐️</emoji>'
    USER           = f'<emoji id="{Emoji.USER}">👤</emoji>'
    USERS          = f'<emoji id="{Emoji.USERS}">👥</emoji>'
    KEY            = f'<emoji id="{Emoji.KEY}">🔑</emoji>'
    FIRE           = f'<emoji id="{Emoji.FIRE}">🔥</emoji>'
    SPARKLE_STAR   = f'<emoji id="{Emoji.SPARKLE_STAR}">🌟</emoji>'

    BACK           = f'<emoji id="{Emoji.BACK}">◀️</emoji>'
    CLOSE          = f'<emoji id="{Emoji.CLOSE}">❌</emoji>'
    HOME           = f'<emoji id="{Emoji.HOME}">🏠</emoji>'
    REFRESH        = f'<emoji id="{Emoji.REFRESH}">🔄</emoji>'
    REPO           = f'<emoji id="{Emoji.REPO}">🔗</emoji>'
    NEXT           = f'<emoji id="{Emoji.NEXT}">➡️</emoji>'
    ADD            = f'<emoji id="{Emoji.ADD}">➕</emoji>'
    PIN            = f'<emoji id="{Emoji.PIN}">📌</emoji>'

    CHAT           = f'<emoji id="{Emoji.CHAT}">💬</emoji>'
    SEND           = f'<emoji id="{Emoji.SEND}">✉️</emoji>'
    ROCKET         = f'<emoji id="{Emoji.ROCKET}">🚀</emoji>'
    GLOBE          = f'<emoji id="{Emoji.GLOBE}">🌐</emoji>'
    LINK           = f'<emoji id="{Emoji.LINK}">🔗</emoji>'
    TOOLS          = f'<emoji id="{Emoji.TOOLS}">🛠️</emoji>'
    KANG           = f'<emoji id="{Emoji.KANG}">🎨</emoji>'
    SUDO           = f'<emoji id="{Emoji.SUDO}">👑</emoji>'
    OWNER          = f'<emoji id="{Emoji.OWNER}">⚙️</emoji>'
    HELP           = f'<emoji id="{Emoji.HELP}">ℹ️</emoji>'


def keycaps(number):
    """123 -> '1️⃣2️⃣3️⃣'. Plain keycaps; HTML.parse upgrades them to the custom
    digit emoji when the bot may send those (see utils/premium_emoji.py)."""
    return "".join(f"{d}️⃣" for d in str(number))

