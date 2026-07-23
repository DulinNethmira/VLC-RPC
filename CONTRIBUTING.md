# Contributing to VLC RPC

Thanks for helping improve VLC RPC.

## Before You Start

1. Check existing issues and pull requests.
2. Use the latest version of the project.
3. Keep changes focused on one problem at a time.

## Development Setup

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app from source:

```bash
python vlc_discord_rpc_gui.py
```

## Bug Reports

Include:

- VLC RPC version
- Windows version
- VLC version
- Discord desktop version
- The exact media filename
- Steps to reproduce
- What you expected
- What actually happened

## Pull Requests

- Keep PRs small and focused.
- Do not include generated build files unless requested.
- Test VLC polling, Discord RPC, cover metadata, and AniList sync when related.
- Update documentation when behavior changes.

