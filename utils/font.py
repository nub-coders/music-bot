"""
utils/font.py — Aesthetic Unicode Font Utilities for NUB Music Bot.

Supported styles (clean typography):
  - small_caps : ɴᴏᴡ ᴘʟᴀʏɪɴɢ
  - bold_serif : 𝐍𝐨𝐰 𝐏𝐥𝐚𝐲𝐢𝐧𝐠
  - bold_sans  : 𝗡𝗼𝘄 𝗣𝗹𝗮𝘆𝗶𝗻𝗴
  - monospace  : 𝙽𝚘𝚠 𝙿𝚕𝚊𝚢𝚒𝚗𝚐
"""

SMALL_CAPS_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


def to_small_caps(text: str) -> str:
    """Converts ASCII letters to Unicode Small Caps."""
    return text.translate(SMALL_CAPS_MAP)


def to_bold_serif(text: str) -> str:
    """Converts alphanumeric text to Mathematical Bold Serif."""
    res = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:      # A-Z
            res.append(chr(0x1D400 + (code - 65)))
        elif 97 <= code <= 122:   # a-z
            res.append(chr(0x1D41A + (code - 97)))
        elif 48 <= code <= 57:    # 0-9
            res.append(chr(0x1D7CE + (code - 48)))
        else:
            res.append(char)
    return "".join(res)


def to_bold_sans(text: str) -> str:
    """Converts alphanumeric text to Mathematical Sans-Serif Bold."""
    res = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:      # A-Z
            res.append(chr(0x1D5D4 + (code - 65)))
        elif 97 <= code <= 122:   # a-z
            res.append(chr(0x1D5EE + (code - 97)))
        elif 48 <= code <= 57:    # 0-9
            res.append(chr(0x1D7EC + (code - 48)))
        else:
            res.append(char)
    return "".join(res)


def to_monospace(text: str) -> str:
    """Converts alphanumeric text to Mathematical Monospace."""
    res = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:      # A-Z
            res.append(chr(0x1D670 + (code - 65)))
        elif 97 <= code <= 122:   # a-z
            res.append(chr(0x1D68A + (code - 97)))
        elif 48 <= code <= 57:    # 0-9
            res.append(chr(0x1D7F6 + (code - 48)))
        else:
            res.append(char)
    return "".join(res)


FONTS = {
    "small_caps": ("Small Caps", to_small_caps),
    "bold_serif": ("Bold Serif", to_bold_serif),
    "bold_sans": ("Bold Sans", to_bold_sans),
    "monospace": ("Monospace", to_monospace),
}


def apply_font(text: str, style: str = "small_caps") -> str:
    """Applies the requested font style to the target text."""
    if style in FONTS:
        return FONTS[style][1](text)
    return text
