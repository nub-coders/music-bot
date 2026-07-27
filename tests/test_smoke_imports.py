"""Smoke test: every importable module loads without a live Mongo/Telegram connection.

Catches import-time regressions cheaply. `main.py` is excluded — it's the entry
point (creates Clients and blocks on idle/login), not an importable library module.
`clients` is pre-seeded with mocks in conftest.py so the plugins' module-level
`clients["session"]` lookup doesn't KeyError at import.
"""
import importlib

import pytest

MODULES = [
    "config", "database", "tools", "youtube", "thumbnails", "sources", "state",
    "plugins._common", "plugins.info",
    "plugins.playback", "plugins.controls", "plugins.queue_cmds",
    "plugins.admin_auth", "plugins.admin_sudo", "plugins.broadcast",
    "plugins.start", "plugins.about", "plugins.meme",
    "plugins.welcome", "plugins.lang_commands",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    importlib.import_module(module)
