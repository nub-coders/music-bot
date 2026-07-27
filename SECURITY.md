# Security Policy

## Reporting a vulnerability

Do **not** open a public issue for security problems.

Report privately via GitHub's [Report a vulnerability](https://github.com/nub-coders/nub-music-bot/security/advisories/new) advisory form, or contact the maintainers in the [support group](https://t.me/nub_coder_s).

Include what you found, how to reproduce it, and the impact. We'll acknowledge within a few days and keep you posted on the fix.

## Handling secrets

- All secrets (`BOT_TOKEN`, `STRING_SESSION`, `MONGODB_URI`, `SPOTIFY_CLIENT_SECRET`, API keys) are supplied via environment variables or a gitignored `.env`. None have baked-in defaults — the bot fails loudly if `MONGODB_URI` is unset.
- If you ever commit a secret by accident, rotate it immediately; git history is public and permanent.
