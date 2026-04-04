"""
Premium Custom Emoji IDs
Curated from the following Telegram emoji packs:
  - L4EVector001_by_fStikBot
  - CenterOfEmoji980633
  - sticks_787a5_by_TgEmodziBot
  - DMJUnigramAnimationEmoji
  - EmojiStatus
  - TgAndroidIcons

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
    BROADCAST      = 5771695636411847302   # 📢  TgAndroidIcons
    PLAY           = 5857290546459973028   # 🚀  DMJUnigramAnimationEmoji (used as Play)
    SKIP           = 5886451926995833684   # ⬇️  TgAndroidIcons (next)
    RESUME         = 5825794181183836432   # ✔️  TgAndroidIcons (resume)
    PAUSE          = 5909201569898827582   # 🔔  TgAndroidIcons (pause indicator)
    STOP           = 5877413297170419326   # 🚫  TgAndroidIcons (stop/end)
    LOOP           = 6005843436479975944   # 🔁  TgAndroidIcons
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
    SUDO           = 5807868868886009920   # 👑  EmojiStatus  (reuse crown)
    OWNER          = 5807868868886009920   # 👑  EmojiStatus
    BROADCAST_BTN  = 5771695636411847302   # 📢  TgAndroidIcons
    AUTH_ICON      = 6005570495603282482   # 🔑  TgAndroidIcons
    BLOCKLIST_ICON = 5877413297170419326   # 🚫  TgAndroidIcons
    HELP           = 5879785854284599288   # ℹ️  TgAndroidIcons
