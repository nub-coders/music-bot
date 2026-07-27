"""Smoke test: every importable module loads without a live Mongo/Telegram connection.

Catches import-time regressions cheaply. `main.py` is excluded — it's the entry
point (creates Clients and blocks on idle/login), not an importable library module.
`clients` is pre-seeded with mocks in conftest.py so plugins.bots's module-level
`clients["session"]` lookup doesn't KeyError at import.
"""
import importlib

import pytest

MODULES = [
    "config", "database", "tools", "youtube",
    "thumbnails", "plugins.bots", "plugins.info",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    importlib.import_module(module)
