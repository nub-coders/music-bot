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
    MIC            = 5897554554894946515   # 🎤  TgAndroidIcons
    BROADCAST      = 5424818078833715060   # 📢  NewsEmoji
    PLAY           = 5775981206319402773   # 🎞  TgAndroidIcons
    SKIP           = 5875506366050734240   # ➡️  TgAndroidIcons
    RESUME         = 5775981206319402773   # 🎞  TgAndroidIcons
    PAUSE          = 5890838600433536921   # 🔇  TgAndroidIcons
    STOP           = 5872829476143894491   # 🚫  TgAndroidIcons
    LOOP           = 5839200986022812209   # 🔄  TgAndroidIcons
    BOLT           = 5843553939672274145   # ⚡️  TgAndroidIcons

    # ── Status / Info ─────────────────────────────────────────────────────────
    NOW_PLAYING    = 5890831539507302154   # 🎵  TgAndroidIcons
    QUEUE_ICON     = 5877316724830768997   # 🗃   TgAndroidIcons
    LOADING        = 5787237370709413702   # ⚙️  DMJUnigramAnimationEmoji
    SETTINGS       = 5787237370709413702   # ⚙️  DMJUnigramAnimationEmoji
    INFO           = 5879785854284599288   # ℹ️  TgAndroidIcons
    STATS          = 5877485980901971030   # 📊  TgAndroidIcons
    PING           = 5843553939672274145   # ⚡️  TgAndroidIcons

    # ── Success / Error ───────────────────────────────────────────────────────
    SUCCESS        = 5776375003280838798   # ✅  TgAndroidIcons
    ERROR          = 5778527486270770928   # ❌  TgAndroidIcons
    WARNING        = 5881702736843511327   # ⚠️  TgAndroidIcons
    BLOCKED        = 5877413297170419326   # 🚫  TgAndroidIcons
    LOCK           = 5879895758202735862   # 🔒  TgAndroidIcons
    UNLOCK         = 6034962180875490251   # 🔓  TgAndroidIcons
    SHIELD         = 5926783847453692661   # 🛡   TgAndroidIcons

    # ── User / Admin ──────────────────────────────────────────────────────────
    CROWN          = 5807868868886009920   # 👑  EmojiStatus
    DIAMOND        = 5963312935148195483   # 💎  TgAndroidIcons
    STAR           = 5807752501042089473   # ⭐️  EmojiStatus
    USER           = 5771887475421090729   # 👤  TgAndroidIcons
    USERS          = 5942877472163892475   # 👥  TgAndroidIcons
    KEY            = 6005570495603282482   # 🔑  TgAndroidIcons
    FIRE           = 6008118472066732010   # 🔥  TgAndroidIcons
    SPARKLE_STAR   = 5989815447459991163   # 🌟  CenterOfEmoji980633

    # ── Navigation / UI ───────────────────────────────────────────────────────
    BACK           = 5877629862306385808   # ◀️  TgAndroidIcons
    CLOSE          = 5778527486270770928   # ❌  TgAndroidIcons
    HOME           = 5967822972931542886   # 🏠  TgAndroidIcons
    REFRESH        = 5877410604225924969   # 🔄  TgAndroidIcons
    REPO           = 5877465816030515018   # 🔗  TgAndroidIcons
    NEXT           = 5877468380125990242   # ➡️  TgAndroidIcons
    ADD            = 5877219383691972108   # ➕  TgAndroidIcons
    PIN            = 5908961403917570106   # 📌  TgAndroidIcons

    # ── Message types ─────────────────────────────────────────────────────────
    CHAT           = 5884179047482659474   # 💬  TgAndroidIcons
    SEND           = 5913236481220022288   # ✉️  DMJUnigramAnimationEmoji
    ROCKET         = 5857290546459973028   # 🚀  DMJUnigramAnimationEmoji
    GLOBE          = 5879585266426973039   # 🌐  TgAndroidIcons
    LINK           = 5778586619380503542   # 🔗  TgAndroidIcons
    TOOLS          = 5988023995125993550   # 🛠   TgAndroidIcons
    KANG           = 5814690801665446789   # 🎨  TgAndroidIcons
    SUDO           = 5807868868886009920   # 👑  EmojiStatus
    OWNER          = 5807868868886009920   # 👑  EmojiStatus
    BROADCAST_BTN  = 5424818078833715060   # 📢  NewsEmoji
    AUTH_ICON      = 6005570495603282482   # 🔑  TgAndroidIcons
    BLOCKLIST_ICON = 5877413297170419326   # 🚫  TgAndroidIcons
    HELP           = 5879785854284599288   # ℹ️  TgAndroidIcons

    # ── News & Announcements (NewsEmoji) ──────────────────────────────────────
    NEWS_BREAKING  = 5456140674028019486   # 🚨  NewsEmoji
    NEWS_URGENT    = 5224607267797606837   # ⚡  NewsEmoji
    NEWS_ALERT     = 5447644880824181073   # ⚠️  NewsEmoji
    NEWS_BROADCAST = 5424818078833715060   # 📢  NewsEmoji
    NEWS_BELL      = 5458603043203327669   # 🔔  NewsEmoji
    NEWS_PIN       = 5397782960512444700   # 📌  NewsEmoji
    NEWS_STATS     = 5231200819986047254   # 📊  NewsEmoji

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

    NEWS_BREAKING  = f'<emoji id="{Emoji.NEWS_BREAKING}">🚨</emoji>'
    NEWS_URGENT    = f'<emoji id="{Emoji.NEWS_URGENT}">⚡</emoji>'
    NEWS_ALERT     = f'<emoji id="{Emoji.NEWS_ALERT}">⚠️</emoji>'
    NEWS_BROADCAST = f'<emoji id="{Emoji.NEWS_BROADCAST}">📢</emoji>'
    NEWS_BELL      = f'<emoji id="{Emoji.NEWS_BELL}">🔔</emoji>'
    NEWS_PIN       = f'<emoji id="{Emoji.NEWS_PIN}">📌</emoji>'
    NEWS_STATS     = f'<emoji id="{Emoji.NEWS_STATS}">📊</emoji>'


def keycaps(number):
    """123 -> '1️⃣2️⃣3️⃣'. Plain keycaps; HTML.parse upgrades them to the custom
    digit emoji when the bot may send those (see utils/premium_emoji.py)."""
    return "".join(f"{d}️⃣" for d in str(number))

