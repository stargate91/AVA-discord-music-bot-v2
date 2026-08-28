# Ava Zea - Discord Radio and Music Bot

Ava Zea is a high-performance, multi-instance Discord music and radio bot built with Python and discord.py. It features a persistent, interactive UI dashboard, fast audio playback via yt-dlp and FFmpeg, SQLite database persistence with WAL mode, intelligent caching, and multi-language support.

---

## Features

### Interactive UI and Dashboard
- Persistent Player Embed: Live track info, dynamic progress bar, cover art, and playback state indicators.
- Interactive Controls: Buttons for Play/Pause, Stop, Skip, Previous (Backtrack), Volume, Seek, Favorite toggle, Queue view, History view, and Help.
- Modal Dialogs: Pop-up input modals for direct Web Link insertion, Search queries, Timestamp jumping (Seeking), and Volume adjustments.
- Select Menus: Switch voice channels, change language, or switch UI display modes on the fly.
- Channel Isolation and Auto-Cleanup: Automatically purges command spam and old UI messages in the dedicated music channel to keep the interface clean.
- Voice Channel Status: Automatically updates the voice channel status string with the current song title.

### Audio Playback and Stream Management
- Broad Source Support: Plays YouTube, SoundCloud, direct audio streams, internet radio feeds, and local audio files using yt-dlp and FFmpeg.
- Seeking: Jump to any specific timestamp (`mm:ss` or total seconds) during live playback.
- Volume Normalization: Dynamic runtime volume scaling without audio clipping.
- Looping Modes: Single track loop and entire queue loop support.
- Queue Management: Add tracks, reorder, shuffle, view paginated queue lists, and navigate backward into history.
- Pre-buffering and Reconnects: Automatic network retry and reconnection arguments passed directly to FFmpeg.

### Multi-Instance Architecture
- Single Codebase, Multiple Bots: Run multiple isolated bot instances concurrently using instance identifiers (e.g., `python main.py 1`, `python main.py 2`).
- Configuration Overlays: Per-instance `.env` and `config<id>.json` support with fallback to default settings.
- Staggered API Sync: Prevents Discord rate-limiting during startup and slash command synchronization across multiple instances.

### Performance and Caching
- Local Audio Cache: Saves downloaded audio streams locally to eliminate redundant downloads and reduce bandwidth usage.
- Ephemeral Mode: Option to automatically purge downloaded audio cache files upon bot startup or shutdown.
- SQLite with WAL Mode: Fast read/write performance with indexed tables for metadata cache, play history, user favorites, and settings.
- Auto-Disconnect: Configurable idle timeouts when left alone in a voice channel or when music stops.

### Localization and Permissions
- Multi-Language Support: Built-in localization support (English `en` and Hungarian `hu`) with per-user language preferences.
- Role-Based Access Control: Dedicated role checks for Admin and Sysadmin operations (cache clearing, remote bot restart).

---

## Prerequisites

- Python 3.10 or higher
- FFmpeg installed and accessible via system PATH (or specified in configuration)
- yt-dlp installed and up to date
- Discord Bot Application with the following Gateway Intents enabled:
  - Message Content Intent
  - Server Members Intent
  - Voice States Intent

---

## Installation

1. Clone the repository:
```bash
git clone https://github.com/stargate91/discord-music-bot.git
cd discord-music-bot
```

2. Create and activate a Python virtual environment:
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate
```

3. Install required Python dependencies:
```bash
pip install -r requirements.txt
```

4. Verify FFmpeg installation:
```bash
ffmpeg -version
```

---

## Configuration

Ava Zea uses environment variables for sensitive credentials and JSON configuration files for behavioral settings.

### 1. Environment Variables (`configs/.env`)

Create a file named `.env` in the `configs/` directory (or use `configs/.env.example` as a template):

```env
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ID=1083433370815582240
RADIO_CHANNEL_ID=1482994023298760894
AUTO_JOIN_ID=0
```

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Discord Bot Application token. |
| `GUILD_ID` | Target Discord Guild (Server) ID for fast slash command sync. |
| `RADIO_CHANNEL_ID` | Dedicated text channel ID where the interactive player lives. |
| `AUTO_JOIN_ID` | Voice channel ID to automatically connect to on startup (`0` to disable). |

### 2. General Configuration (`configs/config.json`)

The primary configuration file defines defaults, UI themes, timeouts, and paths:

```json
{
    "guild_id": 0,
    "radio_text_channel_id": 0,
    "auto_join_channel_id": 0,
    "afk_channel_id": 0,
    "admin_role_id": 0,
    "sysadmin_role_id": 0,
    "default_language": "en",
    "default_ui_mode": "full",
    "update_voice_status": true,
    "forbidden_bot_ids": [],
    "ffmpeg_path": "ffmpeg",
    "ytdlp_path": "yt-dlp",
    "languages": [
        {
            "code": "en",
            "label": "English"
        },
        {
            "code": "hu",
            "label": "Magyar"
        }
    ],
    "ui_settings": {
        "search_items_per_page": 5,
        "queue_items_per_page": 5,
        "player_upcoming_limit": 5,
        "progress_bar_width": 18,
        "thumbnail_size": 40,
        "max_title_len": 45,
        "list_max_title_len": 120,
        "max_uploader_len": 35
    },
    "timings": {
        "embed_refresh_minutes": 58,
        "progress_update_seconds": 15,
        "afk_retry_seconds": 5,
        "solitary_timeout_seconds": 300,
        "action_timeout": 5.0,
        "view_timeout": 60,
        "command_delete_delay": 1.5,
        "notification_timeout": 20.0,
        "ui_cleanup_frequency": 60,
        "message_cleanup_limit": 50,
        "player_loop_sleep": 0.5
    },
    "defaults": {
        "volume": 0.5,
        "prefix": "!",
        "history_limit": 50,
        "search_limit": 20,
        "database_path": "data/radio.db",
        "log_level": "INFO",
        "audio_bitrate": "320k",
        "max_cache_size_mb": 10240,
        "cache_expiry_days": 30,
        "ephemeral_cache": true
    }
}
```

---

## Running the Bot

### Single Instance Mode

To start the default instance:
```bash
python main.py
```

### Multi-Instance Mode

You can run multiple bot instances from the same directory by passing an instance name or number. Each instance loads its corresponding `.env` and `config.json` files:

- Instance `1`: loads `configs/1.env` and `configs/config1.json`
- Instance `2`: loads `configs/2.env` and `configs/config2.json`

```bash
# Start instance 1
python main.py 1

# Start instance 2
python main.py 2

# Start with custom config path
python main.py --config configs/custom_config.json
```

---

## Commands Reference

Ava Zea supports both Slash Commands (`/`) and traditional Prefix Commands (`!`). All commands must be executed in the configured radio text channel.

### Playback Commands

| Slash Command | Prefix Command | Description |
|---|---|---|
| `/play [url]` | `!p [url]`, `!play [url]` | Plays audio from link/search query or resumes paused playback. |
| `/pause` | `!pause` | Pauses current audio playback. |
| `/stop` | `!stop` | Stops playback and clears the active track. |
| `/skip` | `!s`, `!skip` | Skips to the next track in queue. |
| `/back` | `!b`, `!back` | Plays the previous track from history. |
| `/seek [time]` | `!seek [time]` | Seeks to timestamp (`mm:ss` or seconds, e.g. `01:45` or `105`). |
| `/volume [0-100]` | `!v [0-100]`, `!volume [0-100]` | Adjusts playback volume level. |
| `/loop` | `!loop`, `!lt` | Toggles single track looping. |
| `/loopq` | `!loopq`, `!lq` | Toggles entire queue looping. |
| `/shuffle` | `!sh`, `!shuffle` | Randomizes the upcoming track queue. |

### Queue & Navigation Commands

| Slash Command | Prefix Command | Description |
|---|---|---|
| `/queue` | `!q`, `!queue` | Displays the paginated upcoming song queue. |
| `/join` | `!j`, `!join` | Summons the bot to your current voice channel. |
| `/disconnect` | `!d`, `!leave` | Disconnects the bot from the voice channel. |
| `/help` | `!h`, `!help` | Displays command usage and help information. |

### Administrative Commands

| Slash Command | Prefix Command | Permission | Description |
|---|---|---|---|
| `/clearcache` | `!clearcache` | Admin / Sysadmin | Purges cached audio files from local storage. |
| `/restart` | `!restart` | Admin / Sysadmin | Restarts the bot process gracefully. |

---

## Architecture and Project Structure

```
ava-zea/
|-- bot.py                 # Core RadioBot class (extensions, tasks, views)
|-- main.py                # Entry point, CLI argument parsing, instance runner
|-- requirements.txt       # Python dependencies
|-- cogs/                  # Discord command cogs & event listeners
|   |-- admin.py           # Admin operations (clearcache, restart)
|   |-- events.py          # Ready events, voice state updates, auto-join
|   |-- playback.py        # Playback slash commands (play, pause, seek, etc.)
|   |-- prefix_commands.py # Message prefix command parser
|   |-- queue.py           # Queue and loop slash commands
|   |-- radio.py           # Voice channel connection and volume commands
|-- configs/               # Environment variables and JSON configuration files
|   |-- .env.example       # Example environment file
|   |-- config.json        # Base configuration file
|-- core/                  # Bot state and database management
|   |-- actions.py         # Action and state enumerations
|   |-- database.py        # SQLite database wrapper with WAL mode
|   |-- embed_state.py     # Embed view state data holder
|   |-- models.py          # Song and Queue dataclasses
|   |-- state.py           # RadioManager central state controller
|-- locales/               # Localization strings (en, hu)
|-- providers/             # Media extraction and stream providers
|   |-- base.py            # Base audio provider abstraction
|   |-- ytdlp_provider.py  # yt-dlp metadata extraction and caching
|-- services/              # Background workers and business logic
|   |-- audio_player.py    # FFmpeg audio player loop and queue processor
|   |-- cache_service.py   # Audio file disk caching and lifecycle
|   |-- favorites.py       # User favorite tracks management
|   |-- history.py         # Playback history tracker
|   |-- permissions.py     # Channel and voice interaction permission checks
|-- ui/                    # Discord UI components, modals, and views
|   |-- components/        # Action buttons, selects, and progress bars
|   |-- modals/            # Modal forms (search, weblink, seek, volume)
|   |-- views/             # Composite UI views (player, queue, history, search)
|   |-- i18n.py            # Internationalization translation helper
|   |-- manager.py         # UIManager embed lifecycle and message cleanup
|   |-- theme.py           # UI color palettes and styles
|-- utils/                 # General utility modules
|   |-- config.py          # Configuration parser and loader
|   |-- logger.py          # Structured logging utility
```

---

## Database & Storage

Ava Zea uses SQLite with Write-Ahead Logging (WAL) for persistent data storage:
- `song_cache`: Cached track metadata (title, duration, uploader, thumbnail, local path).
- `history`: Comprehensive playback history with user attribution and timestamps.
- `user_settings`: Per-user language, default volume, and UI preferences.
- `favorites`: User-saved favorite tracks and custom radio stations.
- `system_stats`: Global playback counters and metrics.

---

## Troubleshooting

### Bot does not respond to commands
- Ensure the commands are sent in the configured `RADIO_CHANNEL_ID`.
- Check if your Discord user is connected to a voice channel.
- Verify that `Message Content Intent` and `Server Members Intent` are enabled in the Discord Developer Portal.

### Audio is stuttering or failing to play
- Verify that `ffmpeg` is installed and accessible in your system PATH.
- Update `yt-dlp` to the latest version (`pip install --upgrade yt-dlp`).
- Check network stability and ensure sufficient disk space for audio caching.

### Slash commands are not showing up
- Bot slash commands are synced directly to `GUILD_ID` on startup. Ensure the Guild ID in `.env` is correct.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
