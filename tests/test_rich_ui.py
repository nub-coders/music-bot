import pytest
from utils.rich_ui import (
    _normalize_html,
    _plain_fallback,
    rich_heading,
    rich_table,
    rich_kv_table,
    rich_note,
    rich_code,
)


def test_normalize_html_preserves_linebreaks_with_table():
    card = (
        rich_heading("Stats (24h)", 1)
        + rich_table(["#", "Group", "Plays"], [("1", "Test", "10")])
        + rich_note("Collected in: 2.8s\nSnapshot: 10:00:00\nPerformance Summary")
    )
    normalized = _normalize_html(card)

    # Tables should remain intact
    assert '<table border="1"><tr><th>#</th><th>Group</th><th>Plays</th></tr><tr><td>1</td><td>Test</td><td>10</td></tr></table>' in normalized
    # Blockquote content should preserve linebreaks via <br/>\n
    assert "<blockquote>Collected in: 2.8s<br/>\nSnapshot: 10:00:00<br/>\nPerformance Summary</blockquote>" in normalized


def test_normalize_html_preserves_pre_blocks():
    text = "<pre>def foo():\n    return 42\n</pre>\n<blockquote>Note 1\nNote 2</blockquote>"
    normalized = _normalize_html(text)
    assert "<pre>def foo():\n    return 42\n</pre>" in normalized
    assert "<blockquote>Note 1<br/>\nNote 2</blockquote>" in normalized


def test_normalize_html_no_double_br():
    text = "Line 1<br/>\nLine 2<br>\nLine 3"
    normalized = _normalize_html(text)
    assert normalized == "Line 1<br/>\nLine 2<br>\nLine 3"


def test_plain_fallback_with_table_and_note():
    card = (
        rich_heading("Stats (24h)", 1)
        + rich_table(["#", "Group", "Plays"], [("1", "Test", "10")])
        + rich_note("Collected in: 2.8s\nSnapshot: 10:00:00\nPerformance Summary")
    )
    fallback = _plain_fallback(card)
    assert "<b>Stats (24h)</b>" in fallback
    assert "1  Test  10" in fallback
    assert "<blockquote>Collected in: 2.8s\nSnapshot: 10:00:00\nPerformance Summary</blockquote>" in fallback
