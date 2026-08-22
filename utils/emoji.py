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
    TICK           = 5774022692642492953   # ✅  Custom tick
    UNTICK         = 5778479949572738874   # ❌  Custom untick
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
    """Pre-formatted HTML custom emoji tags for messages.

    Always the ``<tg-emoji emoji-id="...">`` spelling, never ``<emoji id="...">``:
    Telegram's server-side Rich Message HTML compiler only recognises the former,
    and silently strips the latter (falling back to the bare Unicode glyph).
    pyrogram's own client-side parser accepts both, so this one spelling is
    correct for plain sends and ``InputRichMessage`` alike.
    """
    MUSIC_NOTE     = f'<tg-emoji emoji-id="{Emoji.MUSIC_NOTE}">🎵</tg-emoji>'
    MUSIC_NOTES    = f'<tg-emoji emoji-id="{Emoji.MUSIC_NOTES}">🎶</tg-emoji>'
    HEADPHONES     = f'<tg-emoji emoji-id="{Emoji.HEADPHONES}">🎧</tg-emoji>'
    MIC            = f'<tg-emoji emoji-id="{Emoji.MIC}">🎤</tg-emoji>'
    BROADCAST      = f'<tg-emoji emoji-id="{Emoji.BROADCAST}">📢</tg-emoji>'
    PLAY           = f'<tg-emoji emoji-id="{Emoji.PLAY}">🎞</tg-emoji>'
    SKIP           = f'<tg-emoji emoji-id="{Emoji.SKIP}">➡️</tg-emoji>'
    RESUME         = f'<tg-emoji emoji-id="{Emoji.RESUME}">🎞</tg-emoji>'
    PAUSE          = f'<tg-emoji emoji-id="{Emoji.PAUSE}">🔇</tg-emoji>'
    STOP           = f'<tg-emoji emoji-id="{Emoji.STOP}">🚫</tg-emoji>'
    LOOP           = f'<tg-emoji emoji-id="{Emoji.LOOP}">🔄</tg-emoji>'
    BOLT           = f'<tg-emoji emoji-id="{Emoji.BOLT}">⚡</tg-emoji>'

    NOW_PLAYING    = f'<tg-emoji emoji-id="{Emoji.NOW_PLAYING}">🎵</tg-emoji>'
    QUEUE_ICON     = f'<tg-emoji emoji-id="{Emoji.QUEUE_ICON}">🗃</tg-emoji>'
    LOADING        = f'<tg-emoji emoji-id="{Emoji.LOADING}">⚙️</tg-emoji>'
    SETTINGS       = f'<tg-emoji emoji-id="{Emoji.SETTINGS}">⚙️</tg-emoji>'
    INFO           = f'<tg-emoji emoji-id="{Emoji.INFO}">ℹ️</tg-emoji>'
    STATS          = f'<tg-emoji emoji-id="{Emoji.STATS}">📊</tg-emoji>'
    PING           = f'<tg-emoji emoji-id="{Emoji.PING}">⚡</tg-emoji>'

    SUCCESS        = f'<tg-emoji emoji-id="{Emoji.SUCCESS}">✅</tg-emoji>'
    ERROR          = f'<tg-emoji emoji-id="{Emoji.ERROR}">❌</tg-emoji>'
    TICK           = f'<tg-emoji emoji-id="{Emoji.TICK}">✅</tg-emoji>'
    UNTICK         = f'<tg-emoji emoji-id="{Emoji.UNTICK}">❌</tg-emoji>'
    WARNING        = f'<tg-emoji emoji-id="{Emoji.WARNING}">⚠️</tg-emoji>'
    BLOCKED        = f'<tg-emoji emoji-id="{Emoji.BLOCKED}">🚫</tg-emoji>'
    LOCK           = f'<tg-emoji emoji-id="{Emoji.LOCK}">🔐</tg-emoji>'
    UNLOCK         = f'<tg-emoji emoji-id="{Emoji.UNLOCK}">🔓</tg-emoji>'
    SHIELD         = f'<tg-emoji emoji-id="{Emoji.SHIELD}">🛡</tg-emoji>'

    CROWN          = f'<tg-emoji emoji-id="{Emoji.CROWN}">👑</tg-emoji>'
    DIAMOND        = f'<tg-emoji emoji-id="{Emoji.DIAMOND}">💎</tg-emoji>'
    STAR           = f'<tg-emoji emoji-id="{Emoji.STAR}">⭐️</tg-emoji>'
    USER           = f'<tg-emoji emoji-id="{Emoji.USER}">👤</tg-emoji>'
    USERS          = f'<tg-emoji emoji-id="{Emoji.USERS}">👥</tg-emoji>'
    KEY            = f'<tg-emoji emoji-id="{Emoji.KEY}">🔑</tg-emoji>'
    FIRE           = f'<tg-emoji emoji-id="{Emoji.FIRE}">🔥</tg-emoji>'
    SPARKLE_STAR   = f'<tg-emoji emoji-id="{Emoji.SPARKLE_STAR}">🌟</tg-emoji>'

    BACK           = f'<tg-emoji emoji-id="{Emoji.BACK}">◀️</tg-emoji>'
    CLOSE          = f'<tg-emoji emoji-id="{Emoji.CLOSE}">❌</tg-emoji>'
    HOME           = f'<tg-emoji emoji-id="{Emoji.HOME}">🏠</tg-emoji>'
    REFRESH        = f'<tg-emoji emoji-id="{Emoji.REFRESH}">🔄</tg-emoji>'
    REPO           = f'<tg-emoji emoji-id="{Emoji.REPO}">🔗</tg-emoji>'
    NEXT           = f'<tg-emoji emoji-id="{Emoji.NEXT}">➡️</tg-emoji>'
    ADD            = f'<tg-emoji emoji-id="{Emoji.ADD}">➕</tg-emoji>'
    PIN            = f'<tg-emoji emoji-id="{Emoji.PIN}">📌</tg-emoji>'

    CHAT           = f'<tg-emoji emoji-id="{Emoji.CHAT}">💬</tg-emoji>'
    SEND           = f'<tg-emoji emoji-id="{Emoji.SEND}">✉️</tg-emoji>'
    ROCKET         = f'<tg-emoji emoji-id="{Emoji.ROCKET}">🚀</tg-emoji>'
    GLOBE          = f'<tg-emoji emoji-id="{Emoji.GLOBE}">🌐</tg-emoji>'
    LINK           = f'<tg-emoji emoji-id="{Emoji.LINK}">🔗</tg-emoji>'
    TOOLS          = f'<tg-emoji emoji-id="{Emoji.TOOLS}">🛠️</tg-emoji>'
    KANG           = f'<tg-emoji emoji-id="{Emoji.KANG}">🎨</tg-emoji>'
    SUDO           = f'<tg-emoji emoji-id="{Emoji.SUDO}">👑</tg-emoji>'
    OWNER          = f'<tg-emoji emoji-id="{Emoji.OWNER}">⚙️</tg-emoji>'
    HELP           = f'<tg-emoji emoji-id="{Emoji.HELP}">ℹ️</tg-emoji>'

    NEWS_BREAKING  = f'<tg-emoji emoji-id="{Emoji.NEWS_BREAKING}">🚨</tg-emoji>'
    NEWS_URGENT    = f'<tg-emoji emoji-id="{Emoji.NEWS_URGENT}">⚡</tg-emoji>'
    NEWS_ALERT     = f'<tg-emoji emoji-id="{Emoji.NEWS_ALERT}">⚠️</tg-emoji>'
    NEWS_BROADCAST = f'<tg-emoji emoji-id="{Emoji.NEWS_BROADCAST}">📢</tg-emoji>'
    NEWS_BELL      = f'<tg-emoji emoji-id="{Emoji.NEWS_BELL}">🔔</tg-emoji>'
    NEWS_PIN       = f'<tg-emoji emoji-id="{Emoji.NEWS_PIN}">📌</tg-emoji>'
    NEWS_STATS     = f'<tg-emoji emoji-id="{Emoji.NEWS_STATS}">📊</tg-emoji>'


def keycaps(number):
    """123 -> '1️⃣2️⃣3️⃣'. Plain keycaps; HTML.parse upgrades them to the custom
    digit emoji when the bot may send those (see utils/premium_emoji.py)."""
    return "".join(f"{d}️⃣" for d in str(number))

