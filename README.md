 # nub-music-bot

[![License](https://img.shields.io/github/license/nub-coders/nub-music-bot?color=0f766e)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Issues](https://img.shields.io/github/issues/nub-coders/nub-music-bot?color=0f766e)](https://github.com/nub-coders/nub-music-bot/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/nub-coders/nub-music-bot?color=0f766e)](https://github.com/nub-coders/nub-music-bot/pulls)
[![Last Commit](https://img.shields.io/github/last-commit/nub-coders/nub-music-bot)](https://github.com/nub-coders/nub-music-bot/commits/main)

 Telegram music/voice-chat bot for streaming audio (and video) into group voice chats.

 ![Bot Logo](music.jpg)

 Summary
 -------
 Lightweight, extensible Python bot built on `Pyrogram` and `pytgcalls` to stream media into Telegram voice chats. This repo contains the bot code, plugins, and utilities used to download, queue and stream media from YouTube and other sources.

 Quick features
 --------------
 - Queue and playback controls (seek, pause, resume, skip)
 - Admin/sudo/owner controls and simple permission management
 - Auto-generated thumbnails and status messages
 - Support for YouTube downloads via `yt-dlp`

 Requirements
 ------------
 - Python 3.10+
 - `ffmpeg` installed on the host
 - MongoDB (or a compatible MongoDB URI)

 Configuration (environment variables)
 -------------------------------------
 The bot reads configuration from environment variables. Key names used by the project (see `config.py`) are:

 - `API_ID` (default in `config.py` shown for convenience)
 - `API_HASH`
 - `BOT_TOKEN`
 - `STRING_SESSION`
 - `OWNER_ID`
 - Optional: `LOGGER_ID`, `DB_NAME`, `YOUTUBE_API_KEYS`, `YTUBE_API_TOKEN` (or `YT_API_TOKEN`), `YTUBE_API_BASE_URL` (or `NUB_YT_API_BASE_URL`)
 - Optional: `YT_COOKIES_FILE` — path to a Netscape-format `cookies.txt` for yt-dlp
   (needed for age-restricted / region-locked videos). Export one from your browser
   and mount it into the container, then point this variable at it. If unset, yt-dlp
   runs without cookies — there is no automatic browser-profile fallback.
 - Optional: `COOKIES_FROM_BROWSER` — one or more browser names (`firefox`,
   `chrome`, `chromium`, `edge`, `brave`, `opera`, `vivaldi`, `safari`, `whale`),
   comma/space-separated. When set, the bot exports cookies from those browsers'
   profiles into `YT_COOKIES_FILE` once at startup (defaulting to `./cookies.txt`
   if `YT_COOKIES_FILE` is unset), trying each in order until one yields a valid
   file. Requires the browser installed and logged in on the host. Best-effort —
   a missing/locked profile just logs a warning and the bot runs without cookies.
   Tune with `COOKIES_BOOTSTRAP_URL` (a URL yt-dlp hits so it exits cleanly and
   validates the cookies) and `COOKIES_REFRESH_HOURS` (re-export interval —
   YouTube rotates tokens mid-session; `0` disables the periodic refresh).
 - Optional: `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` — enable playing Spotify
   track/album/playlist links (resolved to a YouTube search via the Spotify Web API,
   Client Credentials flow — no user login). Create an app at
   https://developer.spotify.com/dashboard and set both. If unset, Spotify links fall
   back to a plain search. Keep the secret out of git.

 Quickstart (local or VPS)
 -------------------------
 1. Clone the repo:

 ```bash
 git clone https://github.com/nub-coders/nub-music-bot.git
 cd nub-music-bot
 ```

 2. Install dependencies:

 ```bash
 python3 -m pip install -r requirements.txt
 ```

 3. Provide environment variables (example using a `.env` file or export commands). At a minimum set `BOT_TOKEN` and either `STRING_SESSION` or Pyrogram credentials.

 4. Run the bot:

 ```bash
 python3 main.py
 ```

 Commands
 --------
 Send these in a group where the bot and assistant are present. Prefix with `/`.

 **Playback**

 | Command | Description |
 |---|---|
 | `/play <query\|url>` | Queue and stream YouTube audio |
 | `/vplay <query\|url>` | Queue and stream YouTube video |
 | `/playforce` · `/vplayforce` | Force play now (skip current) |
 | `/cplay` · `/cvplay` | Play into a linked channel's voice chat |
 | `/cplayforce` · `/cvplayforce` | Force channel play |

 **Controls**

 | Command | Description |
 |---|---|
 | `/pause` · `/resume` | Pause / resume playback |
 | `/skip` | Skip to next track in queue |
 | `/seek <sec>` · `/seekback <sec>` | Seek forward / backward |
 | `/loop <n>` | Loop current track n times (`0` disables) |
 | `/autoplay [on|off]` | Toggle automatic suggestions on queue end (admins only) |
 | `/end` | Stop playback and clear the queue |


 **Queue**

 | Command | Description |
 |---|---|
 | `/queue` | Show the current queue |
 | `/shuffle` | Shuffle the queue |
 | `/del <n>` | Remove item n from the queue |
 | `/cancel` | Cancel the active download/search |

 **Info & tools**

 | Command | Description |
 |---|---|
 | `/start` · `/ping` | Health check and welcome |
 | `/np` · `/nowplaying` | Show the current track |
 | `/lang` · `/setlang` · `/language` | Get/set group language |
 | `/kang` | Steal a sticker into your pack |
 | `/mmf` · `/font` · `/style` | Meme/text styling utilities |

 **Admin & sudo** *(owner/sudo only)*

 | Command | Description |
 |---|---|
 | `/auth` · `/unauth` · `/authlist` | Manage authorized users |
 | `/block` · `/unblock` · `/blocklist` | Manage blocked users |
 | `/addsudo` · `/rmsudo` · `/sudolist` | Manage sudo users |
 | `/tagall` | Mention everyone in the group |
 | `/broadcast` · `/fbroadcast` · `/stats` | Broadcast to chats / show stats |
 | `/reboot` | Restart the bot |

 > Tip: `/start` opens an inline menu that lists these commands by category.

 Deploy
------
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nub-coders/nub-music-bot)

[![Deploy to Halvo](https://halvo.nubcoders.com/deploy/button.svg)](https://app.nubcoders.com/deploy?template=https://github.com/nub-coders/nub-music-bot)

- A `Procfile` and `app.json` are included for easy Heroku deployment (see repository root).

 Contributing
 ------------
 Contributions are welcome. Open issues or PRs with clear descriptions and tests where appropriate.

 License
-------
This project is licensed under the MIT License - see the `LICENSE` file for details.

 Credits
 -------
 Developed by the <img src="https://raw.githubusercontent.com/nub-coders/nub-coders/refs/heads/main/client/public/logo.svg" height="20" align="center" /> Nub Coders community.

 For detailed configuration, inspect `config.py` and `app.json` in the project root.
