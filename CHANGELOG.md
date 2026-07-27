# Changelog

All notable changes to this project are documented here. This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-07-27

First tagged release. Consolidates a multi-phase productionization pass over the original script-grown bot.

### Added
- Test suite (`tests/`) and a GitHub Actions CI workflow (lint + tests on every push).
- Spotify support: track/album/playlist links resolve to YouTube searches via the Spotify Web API (Client Credentials flow, no user login). Enabled by `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`.
- Source-resolver seam (`sources.py`) — a single point where a link/query expands to playable items, so new providers slot in without touching playback.
- YouTube playlist-URL import and a `/shuffle` command.
- Startup cookie export from local browser profile(s) via `COOKIES_FROM_BROWSER` (multiple browsers tried in order), with a periodic refresh (`COOKIES_REFRESH_HOURS`) and a bootstrap-URL validation step.
- Governance docs: `CONTRIBUTING.md`, `SECURITY.md`, issue/PR templates.

### Changed
- Session state (queues/playing/active) externalized behind `SessionStore` with per-chat `asyncio.Lock`, closing the concurrent-activation race.
- Split the `plugins/bots.py` monolith into per-concern modules.
- Collapsed the redundant `get_stream_url` path into `youtube.get_stream`.
- Pinned dependency versions in `requirements.txt` for reproducible installs.

### Security
- Removed hardcoded MongoDB credentials; the bot now fails loudly when `MONGODB_URI` is unset (no baked-in default cluster).
- Added a secret-scanning hook and documented secret handling in `SECURITY.md`.

### Fixed
- Reliability fixes on fragile startup paths, including the browser-cookie handling that could stall startup.
