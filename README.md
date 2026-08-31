# AVA-ZEA - Discord Radio Bot

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-v2.3+-5865F2.svg)](https://github.com/Rapptz/discord.py)
[![CI Workflow](https://github.com/stargate91/discord-music-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/stargate91/discord-music-bot/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-60%20passed-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20core-brightgreen.svg)](tests/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An asynchronous, high-performance Discord music and radio bot built with discord.py and yt-dlp. Features an interactive component-driven user interface, bounded SQLite storage with connection pooling, multi-instance support, robust audio caching, and automated testing with high test coverage.

---

## Interface Preview

<p align="center">
  <img src="https://i.imgur.com/clbaTzy.png" alt="AVA-ZEA Radio Player Interface" width="650"/>
  <br/><br/>
  <img src="https://i.imgur.com/E8sL6OR.png" alt="AVA-ZEA Queue and Settings View" width="650"/>
</p>

---

## Features

- Interactive Discord UI: Control playback, queue navigation, volume, search, history, and favorites through Discord buttons, select menus, and modals.
- Audio Providers: Stream and cache music from YouTube, SoundCloud, direct URLs, and search queries via yt-dlp and FFmpeg.
- Multi-Instance Support: Run multiple independent bot instances concurrently using instance names (for example, `1`, `2`, `radio-a`) with isolated configurations, SQLite databases, cache directories, and log files.
- Thread-Safe SQLite Connection Pool: Database access utilizes connection pooling with WAL mode, parameterized queries, and automatic performance indexes.
- Robust Audio Caching: Automatic caching system with size-bounded LRU cleanup, expired track purge, and optional ephemeral mode on startup.
- Security-First Configuration: Discord bot tokens are strictly isolated to environment variables (`.env`) and rejected if placed inside JSON files. User search inputs are sanitized against command injection and protocol whitelists.
- Localization (i18n): Built-in multilingual support (English and Hungarian) with runtime language switching per user and server.
- High Test Coverage: Comprehensive automated unit and integration test suite with 100% coverage on critical business logic modules.

---

## System Architecture

```
ava-zea/
├── bot.py                  # Custom discord.Client and commands.Bot lifecycle manager
├── main.py                 # CLI entry point, instance parser, and process supervision
├── cogs/                   # Slash command implementations (playback, queue, radio, admin)
├── configs/                # Configuration templates and instance-specific JSON/env files
├── core/
│   ├── actions.py          # State actions and status definitions
│   ├── database.py         # SQLite connection pool, schemas, and queries
│   ├── embed_state.py      # Embed state tracking and updates
│   ├── models.py           # Song dataclass model and serialization
│   └── state.py            # RadioManager state orchestrator and background task manager
├── locales/                # Localization dictionary files (en.json, hu.json)
├── providers/              # yt-dlp audio extraction and playlist resolution
├── services/
│   ├── audio_player.py     # Voice channel streaming loop and playback state machine
│   ├── cache_service.py    # Local disk audio cache and size pruner
│   ├── command_service.py  # User input validation, bounds checking, and action dispatcher
│   ├── favorites.py        # User favorite tracks manager with rate limits and quotas
│   ├── history.py          # Bounded playback history manager
│   ├── permissions.py      # Role and voice channel interaction validator
│   ├── track_resolver.py   # Query sanitization, search, and track resolution
│   └── player/             # AudioSource, prefetcher, and voice channel state manager
├── ui/                     # Discord UI components, views, modals, and themes
├── utils/                  # Config loader with post-init validation and logging setup
└── tests/                  # Pytest test suite and Discord mocks
```

---

## Prerequisites

- Python: Python 3.11, 3.12, or 3.13 (Python 3.14 compatible)
- FFmpeg: Must be installed and accessible in your system PATH (or specified via `ffmpeg_path` in configuration)
- Node.js (Optional): Only if required by specific yt-dlp extractors

---

## Installation

1. Clone the repository:
```bash
git clone https://github.com/stargate91/discord-music-bot.git
cd discord-music-bot
```

2. Create and activate a Python virtual environment:
```bash
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

3. Install production dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Install development and testing dependencies:
```bash
pip install -r requirements-dev.txt
```

---

## Configuration

Configuration values are split between JSON files for operational parameters and `.env` files for secret credentials.

### 1. Environment Variables (.env)

Create a file named `.env` inside the `configs/` directory (or workspace root):

```dotenv
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=0
RADIO_CHANNEL_ID=0
AUTO_JOIN_ID=0
```

Important: Do not put your Discord bot token inside `config.json`. The configuration loader will throw an exception and refuse to start if a token is detected inside JSON files.

### 2. Operational Settings (config.json)

Copy `configs/config.json` to customize operational values:

| Setting | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `guild_id` | integer | `0` | Default Discord server ID (0 for all servers) |
| `radio_text_channel_id` | integer | `0` | Text channel ID for interactive radio embed UI |
| `auto_join_channel_id` | integer | `0` | Voice channel ID to connect automatically on start |
| `admin_role_id` | integer | `0` | Role ID granting bot administrator privileges |
| `sysadmin_role_id` | integer | `0` | Role ID granting system-level bot privileges |
| `default_language` | string | `"hu"` | Default language code (`"en"` or `"hu"`) |
| `default_ui_mode` | string | `"full"` | Default view format (`"full"` or `"compact"`) |
| `ffmpeg_path` | string | `"ffmpeg"` | Path to FFmpeg executable |
| `ytdlp_path` | string | `"yt-dlp"` | Path to yt-dlp executable |
| `defaults.volume` | float | `0.5` | Default playback volume (range: 0.0 to 1.0) |
| `defaults.max_cache_size_mb` | integer | `10240` | Maximum disk size in MB for cached audio files |
| `defaults.ephemeral_cache` | boolean | `true` | When true, purges downloaded cache on startup |

---

## Running the Bot

### Single Instance (Default)
```bash
python main.py
```

### Multi-Instance Mode
Run distinct instances concurrently with dedicated configurations and databases:

```bash
# Runs instance 1 using configs/config1.json and configs/1.env
python main.py 1

# Runs instance 2 using configs/config2.json and configs/2.env
python main.py 2

# Runs with an explicit config file path
python main.py --config /path/to/custom_config.json
```

---

## Slash Commands

All interactions are available as native Discord slash commands:

### Playback Controls
- `/play [url]`: Plays audio from a URL/query, or resumes paused audio.
- `/pause`: Pauses currently playing track.
- `/stop`: Stops playback, clears the current track, and resets state.
- `/skip`: Skips the current track to the next item in the queue.
- `/back`: Navigates back to the previous track recorded in history.
- `/seek <time>`: Jumps to a specific timestamp (e.g. `01:30` or `90`).

### Queue & Modes
- `/queue`: Displays the interactive, paginated upcoming song queue.
- `/loop`: Toggles repeat mode for the current song.
- `/loopq`: Toggles repeat mode for the entire queue.
- `/shuffle`: Shuffles the order of upcoming songs in the queue.

### Voice & Sound
- `/join`: Connects the bot to your current voice channel.
- `/disconnect`: Disconnects the bot from the active voice channel.
- `/volume <percent>`: Sets playback volume between 0% and 100%.

### Administration
- `/clearcache`: Clears cached audio files and resets metadata (Administrator only).
- `/restart`: Safely shuts down and triggers a process restart (Administrator only).

---

## Testing & Quality Assurance

The codebase includes an automated test suite covering configuration validation, SQLite transactions, track resolution, state management, UI component formatting, and command permissions.

### Run Tests
```bash
pytest
```

### Run Tests with Verbose Output
```bash
pytest -v tests/
```

### Measure Code Coverage
```bash
coverage run -m pytest tests/
coverage report -m
```

### Code Formatting and Linting
Check code quality and compliance with Ruff:
```bash
ruff check .
```

To automatically apply safe fixes:
```bash
ruff check --fix .
```

---

## Continuous Integration

A GitHub Actions workflow is configured in `.github/workflows/ci.yml`. On each push or pull request to the `main` or `master` branches, the CI pipeline automatically:
1. Matrix tests across Ubuntu and Windows runners.
2. Evaluates compatibility across Python 3.11, 3.12, and 3.13.
3. Validates Python bytecode compilation via `compileall`.
4. Runs static analysis using `ruff check`.
5. Executes the full Pytest test suite with coverage tracking.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
