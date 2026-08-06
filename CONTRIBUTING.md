# Contributing to nub-music-bot

Thanks for your interest! nub-music-bot is a Telegram music bot built on Pyrogram and pytgcalls for streaming audio into voice chats.

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg installed on your system
- MongoDB (local or cloud URI)
- Telegram API credentials (API_ID, API_HASH)
- A bot token from [@BotFather](https://t.me/BotFather)
- A Pyrogram session string (optional, for the userbot assistant)

### Local Setup

```bash
# Clone the repo
git clone https://github.com/nub-coders/nub-music-bot.git
cd nub-music-bot

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials (see config.py for all variables)

# Run the bot
python3 main.py
```

## Project Structure

```
├── main.py              Bot entry point
├── config.py            Environment configuration
├── plugins/             Command handlers
│   ├── playback.py      /play, /vplay commands
│   ├── controls.py      /pause, /resume, /skip
│   ├── queue_cmds.py    Queue management
│   └── admin_*.py       Admin/sudo/owner controls
├── core/                Bot core logic
└── utils/               Helpers and utilities
```

## Making Changes

1. **Fork and clone** your fork
2. **Create a feature branch** from `main`
3. **Test your changes** in a real group with a voice chat
4. **Keep commits focused** — one logical change per commit
5. **Write clear commit messages**
6. **Open a PR** describing what changed and why

## Code Style

- Follow PEP 8 where practical
- Use meaningful variable names
- Keep functions small and focused
- Add docstrings for non-obvious logic
- Match the existing patterns before introducing new ones

## Testing

- Test in an actual Telegram group with voice chat
- Verify the commands you changed work as expected
- Check that existing commands still work
- Test with both YouTube links and search queries

## Pull Request Guidelines

- Describe what the PR does in the description
- Link any related issues
- Ensure tests pass (run locally)
- Update README if you added commands or changed setup

## Need Help?

- Join the Telegram group: https://t.me/nub_coder_s
- Open an issue with your question
- Check existing issues and PRs first

## License

By contributing, you agree your contributions will be licensed under the same MIT License that covers this project.
