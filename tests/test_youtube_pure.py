import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")

from youtube import (
    parse_dur, format_ind, extract_artist,
    format_number, format_duration, time_to_seconds, extract_video_id,
)


# ── parse_dur ────────────────────────────────────────────────────────────────
def test_parse_dur_full():
    assert parse_dur("PT1H2M3S") == "1:02:03"

def test_parse_dur_minutes_seconds():
    assert parse_dur("PT3M5S") == "3:05"

def test_parse_dur_seconds_only():
    assert parse_dur("PT45S") == "0:45"

def test_parse_dur_invalid():
    assert parse_dur("bad") == "N/A"

def test_parse_dur_none():
    assert parse_dur(None) == "N/A"

def test_parse_dur_empty():
    assert parse_dur("") == "N/A"


# ── format_ind ───────────────────────────────────────────────────────────────
def test_format_ind_crore():
    assert format_ind(20_000_000) == "2.0 Crore"

def test_format_ind_lakh():
    assert format_ind(500_000) == "5.0 Lakh"

def test_format_ind_thousands():
    assert format_ind(5000) == "5.0K"

def test_format_ind_small():
    assert format_ind(999) == "999"

def test_format_ind_zero():
    assert format_ind(0) == "0"

def test_format_ind_invalid():
    assert format_ind("abc") == "0"


# ── extract_artist ───────────────────────────────────────────────────────────
def test_extract_artist_dash():
    assert extract_artist("Artist - Song", "Channel") == "Artist"

def test_extract_artist_no_dash():
    assert extract_artist("Just a Song", "Channel") == "Channel"

def test_extract_artist_empty_title():
    assert extract_artist("", "Channel") == "Channel"

def test_extract_artist_no_channel():
    assert extract_artist("No Dash", "") == "Unknown Artist"


# ── format_number ────────────────────────────────────────────────────────────
def test_format_number_billions():
    assert format_number(1_000_000_000) == "1B"

def test_format_number_millions():
    assert format_number(2_500_000) == "2.5M"

def test_format_number_thousands():
    assert format_number(1500) == "1.5K"

def test_format_number_small():
    assert format_number(999) == "999"

def test_format_number_none():
    assert format_number(None) == "N/A"

def test_format_number_non_digit_string():
    assert format_number("abc") == "N/A"

def test_format_number_digit_string():
    assert format_number("1500") == "1.5K"


# ── format_duration ──────────────────────────────────────────────────────────
def test_format_duration_with_hours():
    assert format_duration(3661) == "01:01:01"

def test_format_duration_minutes():
    assert format_duration(125) == "02:05"

def test_format_duration_zero():
    assert format_duration(0) == "00:00"

def test_format_duration_negative():
    assert format_duration(-1) == "N/A"

def test_format_duration_non_number():
    assert format_duration("bad") == "N/A"


# ── time_to_seconds ──────────────────────────────────────────────────────────
def test_time_to_seconds_mm_ss():
    assert time_to_seconds("3:45") == 225

def test_time_to_seconds_hh_mm_ss():
    assert time_to_seconds("1:00:00") == 3600

def test_time_to_seconds_seconds_only():
    assert time_to_seconds("30") == 30

def test_time_to_seconds_invalid():
    assert time_to_seconds("bad") == 0


# ── extract_video_id ─────────────────────────────────────────────────────────
def test_extract_video_id_standard():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

def test_extract_video_id_short():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

def test_extract_video_id_embed():
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

def test_extract_video_id_no_match():
    assert extract_video_id("https://example.com") is None
