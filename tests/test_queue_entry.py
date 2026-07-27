"""QueueEntry keeps dict-style reads working during the dict->dataclass transition."""
from tools import QueueEntry


def _make(**over):
    base = dict(message="m", title="t", duration="3:00", mode="audio", yt_link="u",
                chat="c", by="b", session="s", thumb="th")
    base.update(over)
    return QueueEntry(**base)


def test_attribute_and_item_access_agree():
    e = _make(stream_url="http://x", _track_id="tid", _yt_task="task")
    assert e.title == "t" == e["title"]
    assert e["_track_id"] == "tid" == e._track_id
    assert e["_yt_task"] == "task"


def test_get_with_and_without_default():
    e = _make()
    assert e.get("duration") == "3:00"       # present field
    assert e.get("stream_url") is None        # defaulted field
    assert e.get("missing", "fallback") == "fallback"  # absent -> default, like dict.get
