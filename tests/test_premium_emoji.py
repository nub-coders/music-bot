"""
Spec for utils/premium_emoji.py — the decide-once premium/custom emoji switch.

Nothing here touches the network, a bot token, api_id/api_hash, or a live chat;
the Telegram client is a stub.

The contract:
  probe_premium_emoji(client, *chat_ids) tries each truthy chat in order and
  returns the FIRST conclusive answer (True/False), or None if none answered.

  apply_premium_emoji(False) rewrites, in place and once:
    EmojiTag.*  '<emoji id="123">🎵</emoji>' -> '🎵'
    Messages.*  the templates f-string-built at import
    Emoji.*     custom emoji document ids     -> None
    Buttons.*   markups built at import       -> icon_custom_emoji_id None
  apply_premium_emoji(True) changes nothing.

  setup_premium_emoji() = probe then apply, with an inconclusive probe
  treated as "available" (the bot's long-standing behaviour).

Run: python -m pytest tests/test_premium_emoji.py -v
"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyrogram.enums import MessageEntityType
from pyrogram.errors import PremiumAccountRequired
from pyrogram.errors.exceptions.forbidden_403 import (
    PremiumAccountRequired as PremiumAccountRequiredForbidden,
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.emoji import Emoji, EmojiTag
from utils.button import Buttons
from utils.message import Messages
from utils.premium_emoji import (
    apply_premium_emoji,
    probe_premium_emoji,
    setup_premium_emoji,
    strip_custom_emoji_markup,
    strip_custom_emoji_text,
)

TAGGED = '<emoji id="5891249688933305846">🎵</emoji> ɴᴏᴡ ᴘʟᴀʏɪɴɢ'
PLAIN = "🎵 ɴᴏᴡ ᴘʟᴀʏɪɴɢ"


def icon_ids(markup):
    return [b.icon_custom_emoji_id for row in markup.inline_keyboard for b in row]


def snapshot(cls):
    return {k: v for k, v in vars(cls).items() if not k.startswith("_")}


class EmojiStateTestBase(unittest.IsolatedAsyncioTestCase):
    """apply_premium_emoji() mutates shared classes by design, so every test
    restores all four of them or it poisons the rest of the suite."""

    def setUp(self):
        for cls in (Emoji, EmojiTag, Messages, Buttons):
            for name, value in snapshot(cls).items():
                self.addCleanup(setattr, cls, name, value)


class TestBakePlain(EmojiStateTestBase):
    """1. available=False rewrites every surface custom emoji can hide in."""

    def test_emojitag_strings_collapse_to_plain_glyphs(self):
        self.assertIn("<emoji", EmojiTag.MUSIC_NOTE, "guard the premise")

        apply_premium_emoji(False)

        self.assertEqual(EmojiTag.MUSIC_NOTE, "🎵")
        tagged_left = [k for k, v in snapshot(EmojiTag).items()
                       if isinstance(v, str) and "<emoji" in v]
        self.assertEqual(tagged_left, [], "no EmojiTag entry may keep a tag")

    def test_message_templates_baked_at_import_are_rewritten(self):
        self.assertIn("<emoji", Messages.PLAY, "guard the premise")

        apply_premium_emoji(False)

        tagged_left = [k for k, v in snapshot(Messages).items()
                       if isinstance(v, str) and "<emoji" in v]
        self.assertEqual(tagged_left, [], "all 112 templates must be rewritten")
        self.assertIn("ɴᴏᴡ ᴘʟᴀʏɪɴɢ", Messages.PLAY, "template text must survive")
        self.assertIn("{1}", Messages.PLAY, "format placeholders must survive")

    def test_emoji_ids_become_none_so_later_buttons_carry_no_icon(self):
        self.assertIsInstance(Emoji.CLOSE, int, "guard the premise")

        apply_premium_emoji(False)

        self.assertIsNone(Emoji.CLOSE)
        self.assertEqual([k for k, v in snapshot(Emoji).items() if isinstance(v, int)], [])
        # the real payoff: markups built AFTER the bake
        self.assertEqual(icon_ids(Buttons.playback_markup()), [None] * 5)

    def test_markups_built_at_import_are_stripped_too(self):
        self.assertTrue(any(i is not None for i in icon_ids(Buttons.HELP_HOME)),
                        "guard the premise")

        apply_premium_emoji(False)

        self.assertEqual(icon_ids(Buttons.HELP_HOME), [None] * 11)
        self.assertEqual(icon_ids(Buttons.BACK), [None])
        self.assertEqual(Buttons.HELP_HOME.inline_keyboard[0][0].callback_data,
                         "commands_playback", "button wiring must survive")

    def test_bake_is_idempotent(self):
        apply_premium_emoji(False)
        once = (EmojiTag.MUSIC_NOTE, Messages.PLAY, icon_ids(Buttons.HELP_HOME))

        apply_premium_emoji(False)

        self.assertEqual((EmojiTag.MUSIC_NOTE, Messages.PLAY, icon_ids(Buttons.HELP_HOME)), once)


class TestBakePremium(EmojiStateTestBase):
    """2. available=True must not touch anything."""

    def test_nothing_changes(self):
        before = (snapshot(EmojiTag), snapshot(Messages), snapshot(Emoji),
                  icon_ids(Buttons.HELP_HOME))

        self.assertTrue(apply_premium_emoji(True))

        self.assertEqual((snapshot(EmojiTag), snapshot(Messages), snapshot(Emoji),
                          icon_ids(Buttons.HELP_HOME)), before)
        self.assertIn("<emoji", Messages.PLAY)


class TestProbe(EmojiStateTestBase):
    """3. The probe itself: send, read back, delete either way."""

    def client(self, entities, unreachable=()):
        c = SimpleNamespace()
        c.probed = []

        async def send_message(chat_id, *a, **kw):
            c.probed.append(chat_id)
            if chat_id in unreachable:
                raise ValueError(f"PEER_ID_INVALID: {chat_id}")
            return SimpleNamespace(id=42)

        c.send_message = send_message
        c.get_messages = AsyncMock(return_value=SimpleNamespace(entities=entities))
        c.delete_messages = AsyncMock()
        return c

    async def test_entity_echoed_back_is_yes(self):
        c = self.client([SimpleNamespace(type=MessageEntityType.CUSTOM_EMOJI)])
        self.assertIs(await probe_premium_emoji(c, -100123), True)
        c.delete_messages.assert_awaited_once_with(-100123, 42)

    async def test_entity_silently_stripped_is_no(self):
        """The case no exception can catch — and the reason this probe exists."""
        c = self.client([SimpleNamespace(type=MessageEntityType.BOLD)])
        self.assertIs(await probe_premium_emoji(c, -100123), False)
        c.delete_messages.assert_awaited_once_with(-100123, 42)

    async def test_no_entities_is_no(self):
        c = self.client(None)
        self.assertIs(await probe_premium_emoji(c, -100123), False)

    async def test_logger_id_wins_owner_id_untouched(self):
        c = self.client([SimpleNamespace(type=MessageEntityType.CUSTOM_EMOJI)])
        self.assertIs(await probe_premium_emoji(c, "-1001111", 6076474757), True)
        self.assertEqual(c.probed, [-1001111], "a conclusive LOGGER_ID ends the chain")

    async def test_falls_through_to_owner_id(self):
        c = self.client([SimpleNamespace(type=MessageEntityType.CUSTOM_EMOJI)],
                        unreachable=(-1001111,))
        self.assertIs(await probe_premium_emoji(c, "-1001111", 6076474757), True)
        self.assertEqual(c.probed, [-1001111, 6076474757], "must fall through in order")

    async def test_falsy_chat_ids_skipped(self):
        c = self.client([SimpleNamespace(type=MessageEntityType.CUSTOM_EMOJI)])
        await probe_premium_emoji(c, None, "", 6076474757)
        self.assertEqual(c.probed, [6076474757])

    async def test_no_usable_chat_is_inconclusive(self):
        c = self.client(None, unreachable=(-1001111, 6076474757))
        self.assertIsNone(await probe_premium_emoji(c, "-1001111", 6076474757))

    async def test_both_premium_error_codes_mean_no(self):
        """Telegram returns PREMIUM_ACCOUNT_REQUIRED as 400 AND 403, which
        kurigram models as two unrelated classes."""
        self.assertFalse(issubclass(PremiumAccountRequiredForbidden, PremiumAccountRequired),
                         "guard the premise: if kurigram unifies these, this is moot")
        for exc in (PremiumAccountRequired(), PremiumAccountRequiredForbidden()):
            with self.subTest(code=type(exc).__module__):
                c = self.client(None)
                c.send_message = AsyncMock(side_effect=exc)
                self.assertIs(await probe_premium_emoji(c, -100123), False)


class TestSetupEndToEnd(EmojiStateTestBase):
    """4. probe + bake together — what main.py actually calls."""

    def client(self, entity_type=None, fail=None):
        c = SimpleNamespace()
        c.send_message = AsyncMock(side_effect=fail) if fail else AsyncMock(
            return_value=SimpleNamespace(id=42))
        entities = [SimpleNamespace(type=entity_type)] if entity_type else []
        c.get_messages = AsyncMock(return_value=SimpleNamespace(entities=entities))
        c.delete_messages = AsyncMock()
        return c

    async def test_no_premium_bakes_everything_plain(self):
        result = await setup_premium_emoji(self.client(MessageEntityType.BOLD), -100123)

        self.assertFalse(result)
        self.assertEqual(EmojiTag.MUSIC_NOTE, "🎵")
        self.assertNotIn("<emoji", Messages.PLAY)
        self.assertEqual(icon_ids(Buttons.HELP_HOME), [None] * 11)
        self.assertEqual(icon_ids(Buttons.playback_markup()), [None] * 5)

    async def test_premium_leaves_custom_emoji_in_place(self):
        result = await setup_premium_emoji(
            self.client(MessageEntityType.CUSTOM_EMOJI), -100123)

        self.assertTrue(result)
        self.assertIn("<emoji", Messages.PLAY)
        self.assertIsInstance(Emoji.CLOSE, int)

    async def test_inconclusive_probe_keeps_custom_emoji(self):
        """No usable chat must not silently downgrade a Premium bot."""
        result = await setup_premium_emoji(self.client(fail=ValueError("no chat")), -100123)

        self.assertTrue(result)
        self.assertIn("<emoji", Messages.PLAY)


class TestStripHelpers(unittest.TestCase):
    """5. The two strippers in isolation."""

    def test_strip_text(self):
        cases = [
            (TAGGED, PLAIN),
            ('<emoji id="1">🎵</emoji> a <emoji id="22">🎶</emoji>', "🎵 a 🎶"),
            ("<b>bold</b> and <code>code</code> survive", "<b>bold</b> and <code>code</code> survive"),
            ("no tags at all", "no tags at all"),
            ("", ""),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(strip_custom_emoji_text(raw), expected)

    def test_strip_markup_preserves_everything_else(self):
        mixed = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("with icon", callback_data="a", icon_custom_emoji_id=999),
                InlineKeyboardButton("without icon", callback_data="b"),
            ],
            [InlineKeyboardButton("url btn", url="https://t.me/x", icon_custom_emoji_id=888)],
        ])

        stripped = strip_custom_emoji_markup(mixed)

        self.assertEqual(icon_ids(stripped), [None, None, None])
        self.assertEqual(icon_ids(mixed), [999, None, 888], "input must not be mutated")
        flat = stripped.inline_keyboard
        self.assertEqual(flat[0][0].text, "with icon")
        self.assertEqual(flat[0][1].callback_data, "b")
        self.assertEqual(flat[1][0].url, "https://t.me/x")
        self.assertIsNone(strip_custom_emoji_markup(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
