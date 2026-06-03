 # nub-music-bot

 Telegram music/voice-chat bot for streaming audio (and video) into group voice chats.

 ![Bot Logo](https://raw.githubusercontent.com/nub-coders/nub-music-bot/refs/heads/main/music.jpg)

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
 - `MONGODB_URI`
 - Optional: `LOGGER_ID`, `DB_NAME`, `YOUTUBE_API_KEYS`, `YT_API_TOKEN`, `NUB_YT_API_BASE_URL`

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

 Deploy
------
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nub-coders/nub-music-bot)
[![Deploy to Deplox](https://app.nubcoder.com/deploy/button.svg)](https://app.nubcoder.com/deploy?template=https://github.com/nub-coders/nub-music-bot)

- A `Procfile` and `app.json` are included for easy Heroku deployment (see repository root).

 Contributing
 ------------
 Contributions are welcome. Open issues or PRs with clear descriptions and tests where appropriate.

 License
-------
This project is licensed under the MIT License - see the `LICENSE` file for details.

 Credits
 -------
 Developed by the Nub Coders community.

 For detailed configuration, inspect `config.py` and `app.json` in the project root.
