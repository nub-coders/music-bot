<h1 align="center">Telegram Music Bot 🎵</h1>
<p align="center">
  <img src="https://raw.githubusercontent.com/nub-coders/nub-music-bot/refs/heads/main/music.jpg" alt="Bot Logo" width="200"/>
</p>

<p align="center">
  <b>🔥 Ultimate Telegram Voice Chat Music Bot with breathtaking streaming capabilities!</b><br>
  Powered by cutting-edge Pyrogram (Kurigram) and next-gen PyTgCalls for lightning-fast performance. Experience crystal-clear HD audio/video streaming with stunning UI and advanced features that will revolutionize your group voice chats! ⚡✨
</p>

## ✨ Features
- 🎧 **Crystal Clear Audio/Video:** Stream HD audio and video to Telegram Voice Chats seamlessly.
- ⏭️ **Queue Management:** Smart queue system, ability to view queue (`/queue`) and skip tracking.
- ⏯️ **Playback Controls:** Seek (`/seek`, `/seekback`), pause, resume, and skip media directly in the chat.
- ⚡ **Lightning Fast:** Uses `PyTgCalls` and `Kurigram` under the hood for low latency and high stability, taking full advantage of the `uvloop` magic.
- 🛡️ **Advanced Permissions:** Robust admin management including owner access, sudoers, authorized users list (`/auth`, `/unauth`), and blocklists (`/block`, `/unblock`).
- 🔄 **Real-time Status:** View active voice calls and current playing statuses across all groups (`/ac`).
- 🎨 **Beautiful UI:** Auto-generated dynamic images and stylized thumbnails for tracks along with stylish font support.

## 🚀 Recommended Deployment

### Deploy to Heroku
Deploying to Heroku is the easiest way to get your bot running fast. Click the button below to deploy!

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/nub-coders/nub-music-bot)

### Local / VPS Deployment
If you prefer running the bot on your own server or a VPS locally:

#### 1. Requirements 
- Python 3.10+ (Recommended Python 3.13)
- `ffmpeg` installed on the system
- MongoDB (Database)

#### 2. Get your credentials
You will need to fetch your variables and set them in your environment:
- `API_ID` & `API_HASH` from [my.telegram.org](https://my.telegram.org)

- `BOT_TOKEN` from [@BotFather](https://t.me/BotFather)
- `OWNER_ID`: Your Telegram User ID.
- `STRING_SESSION`: A valid Pyrogram session string to act as the music assistant account.
- `MONGODB_URI`: Connectstring for MongoDB instance.

#### 3. Clone & Run
```bash
git clone https://github.com/nub-coders/nub-music-bot.git
cd nub-music-bot
pip install -r requirements.txt
# Set environment variables from app.json
python3 main.py
```

## 🛠️ Stack / Technologies Used
- **Language:** Python
- **Bot Framework:** [Pyrogram](https://github.com/pyrogram/pyrogram) / Kurigram
- **Calling Engine:** [PyTgCalls](https://github.com/pytgcalls/pytgcalls)
- **Database:** MongoDB (`motor`, `pymongo`)
- **Media Download/Extraction:** `yt-dlp`, `youtube-search-python`, `imageio`, `mutagen`
- **Image Processing:** `Pillow`

<p align="center">
  <i>Developed and crafted with ❤️ by <a href="https://t.me/nub_coders">Nub Coders</a></i>
</p>
