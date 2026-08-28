"""Tests for the thumbnail download path in thumbnails.py.

The download used to call `aiofiles.open` without `async with` (leaving the handle
for the garbage collector when the write or the socket read raised) and read the
whole body with `resp.read()` under no size cap and no request timeout.
"""
import aiohttp
import pytest

import thumbnails


class FakeContent:
    def __init__(self, chunks, raise_at=None):
        self.chunks = chunks
        self.raise_at = raise_at

    async def iter_chunked(self, size):
        for index, chunk in enumerate(self.chunks):
            if self.raise_at is not None and index == self.raise_at:
                raise aiohttp.ClientError("connection reset mid-body")
            yield chunk


class FakeResp:
    def __init__(self, chunks=(b"png-bytes",), content_length=None, raise_at=None):
        self.status = 200
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        self.content = FakeContent(list(chunks), raise_at)


async def test_writes_body_and_reports_success(tmp_path):
    dest = tmp_path / "thumb.png"

    assert await thumbnails._download_thumb(FakeResp([b"abc", b"def"]), str(dest)) is True
    assert dest.read_bytes() == b"abcdef"


async def test_empty_body_is_not_treated_as_a_thumbnail(tmp_path):
    dest = tmp_path / "thumb.png"

    assert await thumbnails._download_thumb(FakeResp([]), str(dest)) is False


async def test_oversized_content_length_is_refused_before_writing(tmp_path):
    """Cheap pre-check: refuse on the declared size without opening the file."""
    dest = tmp_path / "thumb.png"
    resp = FakeResp([b"x"], content_length=thumbnails._THUMB_MAX_BYTES + 1)

    assert await thumbnails._download_thumb(resp, str(dest)) is False
    assert not dest.exists()


async def test_oversized_body_is_refused_mid_stream(tmp_path, monkeypatch):
    """A lying or absent Content-Length must not get past the cap."""
    monkeypatch.setattr(thumbnails, "_THUMB_MAX_BYTES", 1024)
    dest = tmp_path / "thumb.png"
    resp = FakeResp([b"y" * 512, b"y" * 512, b"y" * 512])

    assert await thumbnails._download_thumb(resp, str(dest)) is False


async def test_declared_size_within_cap_is_accepted(tmp_path):
    dest = tmp_path / "thumb.png"

    assert await thumbnails._download_thumb(FakeResp([b"ok"], content_length=2), str(dest)) is True


async def test_non_numeric_content_length_does_not_crash(tmp_path):
    dest = tmp_path / "thumb.png"
    resp = FakeResp([b"ok"])
    resp.headers["Content-Length"] = "not-a-number"

    assert await thumbnails._download_thumb(resp, str(dest)) is True


class RecordingFile:
    """Stand-in for an aiofiles handle that records whether it was closed."""

    def __init__(self, path):
        self.path = path
        self.closed = False
        self.written = bytearray()

    async def write(self, chunk):
        self.written.extend(chunk)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True
        return False


@pytest.fixture
def opened_files(monkeypatch):
    handles = []

    def _open(path, mode="wb"):
        handle = RecordingFile(path)
        handles.append(handle)
        return handle

    monkeypatch.setattr(thumbnails.aiofiles, "open", _open)
    return handles


async def test_file_is_closed_when_the_body_read_fails(opened_files, tmp_path):
    """Regression: the bare open/write/close sequence left closing to the garbage
    collector, so the handle stayed open for as long as the raised traceback kept
    the frame alive. `async with` closes it on the way out."""
    with pytest.raises(aiohttp.ClientError):
        await thumbnails._download_thumb(FakeResp([b"a", b"b"], raise_at=1), str(tmp_path / "t.png"))

    assert len(opened_files) == 1
    assert opened_files[0].closed is True


async def test_file_is_closed_when_the_cap_aborts_the_download(opened_files, tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnails, "_THUMB_MAX_BYTES", 8)

    assert await thumbnails._download_thumb(FakeResp([b"y" * 16]), str(tmp_path / "t.png")) is False
    assert opened_files[0].closed is True


def test_session_carries_a_timeout():
    """Without an explicit timeout the fetch inherits aiohttp's 5-minute default."""
    assert thumbnails._THUMB_TIMEOUT.total is not None
    assert thumbnails._THUMB_TIMEOUT.total <= 60
