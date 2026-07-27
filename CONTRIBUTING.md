# Contributing

## Setup

```bash
git clone https://github.com/nub-coders/nub-music-bot.git
cd nub-music-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio ruff
cp .env.example .env  # fill in BOT_TOKEN, STRING_SESSION, MONGODB_URI
```

System deps: `ffmpeg`, `libmagic1` (e.g. `apt install ffmpeg libmagic1`).

## Before opening a PR

```bash
ruff check .                                      # lint
MONGODB_URI=mongodb://localhost:27017/test pytest tests/ -q  # tests
```

Both must pass. CI runs the same checks on every push.

## Guidelines

- One logical change per PR. Keep diffs small.
- New behaviour → add or update a test in `tests/`.
- Match the surrounding code style (comment density, naming, async patterns).
- Don't add a dependency for something a few lines of stdlib can do.
- Secrets and credentials never go in code or committed files — use `.env` (gitignored).

## Reporting bugs

Open a GitHub issue using the bug-report template. Include the relevant log lines and the steps to reproduce.
