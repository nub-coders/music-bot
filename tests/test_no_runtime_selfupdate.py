"""Guards against the bot mutating its own dependencies at runtime.

Startup used to run `pip install -U yt-dlp`, which made the deployed version
unreproducible, executed remote code as a side effect of booting, and blocked the
event loop for up to ~130s. These tests fail if that behaviour comes back.
"""
import asyncio
import importlib.metadata
import subprocess
from pathlib import Path

import main
import youtube

PROJECT_ROOT = Path(youtube.__file__).parent
SKIP_DIRS = {".venv", "tests", "__pycache__", "scratch", "cache", ".git"}


def _project_sources():
    for path in PROJECT_ROOT.rglob("*.py"):
        if SKIP_DIRS & set(path.parts):
            continue
        yield path


def test_self_update_helpers_are_gone():
    assert not hasattr(youtube, "update_ytdlp")
    assert not hasattr(youtube, "is_ytdlp_updated")
    assert not hasattr(youtube, "check_and_update_ytdlp")


def test_pip_machinery_imports_are_gone():
    """`sys`, `subprocess` and `requests` were imported in youtube.py solely for
    the self-upgrade path."""
    assert not hasattr(youtube, "subprocess")
    assert not hasattr(youtube, "requests")
    assert not hasattr(youtube, "sys")


def test_no_source_file_reinvokes_pip():
    """Looks for the code construct rather than prose: a quoted "pip" argument in
    an argv list. os.execl(sys.executable, ...) in /reboot is a legitimate
    self-restart and is deliberately not flagged here."""
    offenders = []
    for path in _project_sources():
        src = path.read_text(encoding="utf-8", errors="replace")
        if '"pip"' in src or "'pip'" in src:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == [], f"runtime pip invocation found in: {offenders}"


def test_youtube_does_not_reinvoke_the_interpreter():
    src = Path(youtube.__file__).read_text(encoding="utf-8")
    assert "sys.executable" not in src
    assert "subprocess.run" not in src


def test_log_ytdlp_version_reports_installed_version():
    assert youtube.log_ytdlp_version() == importlib.metadata.version("yt-dlp")


def test_log_ytdlp_version_spawns_no_process(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("startup must not spawn a subprocess")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(subprocess, "check_output", _forbidden)

    youtube.log_ytdlp_version()


def test_log_ytdlp_version_survives_missing_package(monkeypatch):
    def _missing(_name):
        raise importlib.metadata.PackageNotFoundError("yt-dlp")

    monkeypatch.setattr(importlib.metadata, "version", _missing)
    assert youtube.log_ytdlp_version() is None


def test_log_ytdlp_version_swallows_unexpected_errors(monkeypatch):
    def _boom(_name):
        raise RuntimeError("metadata backend exploded")

    monkeypatch.setattr(importlib.metadata, "version", _boom)
    assert youtube.log_ytdlp_version() is None, "startup must not die over a version log"


def test_log_ytdlp_version_is_synchronous():
    """It is called unawaited from main(); a coroutine here would silently no-op."""
    assert not asyncio.iscoroutinefunction(youtube.log_ytdlp_version)


def test_main_uses_the_passive_logger():
    assert not hasattr(main, "check_and_update_ytdlp")
    assert main.log_ytdlp_version is youtube.log_ytdlp_version
