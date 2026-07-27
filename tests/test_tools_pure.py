import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")

from tools import convert_bytes, trim_title


# ── convert_bytes ────────────────────────────────────────────────────────────
def test_convert_bytes_gib():
    # while size > power is strict: 1024**3 stops at MiB tier (1024.00 MiB)
    assert convert_bytes(1024 ** 3) == "1024.00 MiB"

def test_convert_bytes_mib():
    assert convert_bytes(1024 ** 2) == "1024.00 KiB"

def test_convert_bytes_kib():
    assert convert_bytes(1024) == "1024.00  B"

def test_convert_bytes_bytes():
    assert convert_bytes(512) == "512.00  B"

def test_convert_bytes_zero():
    assert convert_bytes(0) == ""

def test_convert_bytes_none():
    assert convert_bytes(None) == ""


# ── trim_title ───────────────────────────────────────────────────────────────
def test_trim_title_short():
    assert trim_title("Short Title") == "Short Title"

def test_trim_title_long_words():
    title = "one two three four five six seven eight nine ten eleven"
    result = trim_title(title)
    assert len(result.split()) <= 10

def test_trim_title_long_chars():
    title = "A" * 40
    result = trim_title(title)
    assert len(result) <= 30

def test_trim_title_empty():
    assert trim_title("") == ""

def test_trim_title_none():
    assert trim_title(None) == ""
