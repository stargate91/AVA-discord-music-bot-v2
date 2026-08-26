# 🎵 DC Radio Bot - Professional Discord Audio System

A highly modular, enterprise-grade Discord music bot built with **discord.py**, featuring a modern interactive UI, robust playback engine, and a standardized feedback system.

---

## ✨ Key Features

- **🚀 Advanced Playback Navigation**: Browser-like non-destructive history traversal. Move back (`BACK`) and forward (`NEXT`) through your session without losing your queue or duplicating entries.
- **📱 Premium Modern UI**: Built with a custom layout system (`LayoutView`, `Container`, `ActionRow`) providing a sleek aesthetic. Includes dynamic progress bars, status icons, and real-time updates.
- **💬 Standardized UI Feedback**: Every interaction (buttons, slash commands, prefix commands) provides immediate confirmation with icon-prefixed, auto-deleting messages (default 20s).
- **🛡️ Smart Error Handling**: Distinguishes between critical failures (❌ `Icons.ERROR`) and user guidance (⚠️ `Icons.WARNING`). Features private (ephemeral) error messages for out-of-channel usage.
- **🎨 Dynamic Icon & Emoji System**: Fully configurable icons via JSON with a robust three-tier fallback: `Instance Config` -> `Global Config` -> `Hardcoded Unicode Classics`.
- **📚 Persistent History & Favorites**: Fully persistent playback history and personal favorites stored in SQLite, allowing users to build their own collections.
- **🌍 Native Multi-language**: Built-in English and Hungarian support using a centralized localization engine (`hu.json`/`en.json`).
- **🛠️ Multi-Instance Ready**: Run multiple isolated bots from the same codebase. Use the `INSTANCE_NAME` environment variable to separate configurations and databases.

---

## 🛠️ Installation & Setup

### 1. Requirements
- **Python 3.10+**
- **FFmpeg**: Must be available in your system's PATH.
- **yt-dlp**: Required for metadata resolution and stream extraction.

### 2. Setup
```bash
# Clone the repository
git clone <repo-url>
cd dc_radio_bot

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
1. Create a `.env` file in the root or `configs/` directory.
2. Add your `DISCORD_TOKEN` and `GUILD_ID`.
3. (Optional) Set `INSTANCE_NAME=bot1` to use `config.bot1.json` and `radio.bot1.db`.
4. Define your `radio_text_channel_id` in the relevant JSON config.

---

## 📂 Project Architecture

The project follows a clean, layered, modular architecture:

```
dc_radio_bot/
├── configs/                     # Configuration files (.json, .env)
├── locales/                     # Localization files (hu.json, en.json)
├── data/                        # SQLite database and audio cache
│
├── core/                        # State, domain models & action dispatching
│   ├── actions.py               # RadioAction and RadioState enums
│   ├── models.py                # Song dataclass
│   ├── state.py                 # RadioManager state coordinator
│   ├── embed_state.py           # EmbedStateManager
│   └── database.py              # SQLite storage engine
│
├── services/                    # Backend business services
│   ├── audio_player.py          # RadioPlayer (FFmpeg streaming & voice loop)
│   ├── cache_service.py         # CacheService (yt-dlp download & LRU cleanup)
│   ├── permissions.py           # PermissionService (role & channel checks)
│   ├── favorites.py             # FavoriteManager
│   └── history.py               # HistoryManager
│
├── providers/                   # Media metadata & stream resolvers
│   ├── base.py                  # BaseProvider interface
│   └── ytdlp_provider.py        # YouTube / SoundCloud extractor
│
├── ui/                          # User interface components & views
│   ├── manager.py               # UIManager (controller coordinator)
│   ├── icons.py                 # Centralized icon registry & fallback logic
│   ├── theme.py                 # Theme color tokens
│   ├── i18n.py                  # Localization engine (t())
│   ├── utils.py                 # UI feedback, delay delete, duration helpers
│   ├── components/              # Modular UI elements
│   │   ├── progress_bar.py      # Dynamic progress bar builder
│   │   ├── player_controls.py   # Playback, volume, channel & style controls
│   │   └── list_controls.py     # Queue management, favorites & history controls
│   ├── views/                   # Interactive Discord Views
│   │   ├── base.py              # BaseView, PaginatedView, handle_ui_error
│   │   ├── player.py            # NowPlayingView, FrequencyStationView, WelcomeLayout
│   │   ├── queue.py             # FullQueueView
│   │   ├── favorites.py         # FavoritesView
│   │   ├── history.py           # HistoryView
│   │   └── search_results.py    # SearchResultsView
│   └── modals/                  # Interactive Modals
│       ├── search.py            # SearchModal
│       ├── weblink.py           # WebLinkModal
│       ├── volume.py            # VolumeModal
│       └── seek.py              # SeekModal
│
├── cogs/                        # Discord.py Extensions & Commands
│   ├── playback.py              # /play, /pause, /stop, /skip, /back, /seek
│   ├── queue.py                 # /queue, /loop, /loopq, /shuffle
│   ├── radio.py                 # /join, /disconnect, /volume
│   ├── admin.py                 # /clearcache, /restart
│   ├── events.py                # Gateway events & voice state updates
│   └── prefix_commands.py       # Traditional text prefix commands handler
│
├── utils/                       # Utility packages
│   ├── logger.py                # Colored terminal logger
│   └── config.py                # Configuration loader & dataclass
│
├── bot.py                       # RadioBot (commands.Bot subclass)
└── main.py                      # Application entry point & CLI parser
```

---

## 🛠️ Engineering Principles

- **Action Dispatcher Pattern**: All state changes are driven by `RadioAction` enums, ensuring predictable and traceable behavior.
- **Decoupled Design**: The UI, Audio Player, and State Manager are strictly separated; the UI only reflects the State and dispatches Actions.
- **Modular Cogs**: Commands and events are organized into self-contained Discord.py Cogs.
- **Single Responsibility UI**: Views, modals, and interactive buttons are split into dedicated, reusable components.
- **Automatic Cleanup**: Intelligent monitoring (`_cleanup_stray_messages`) keeps the radio channel clean by sweeping old controllers.

---

## 📝 Contribution
Found a bug? Have a feature request? Feel free to open an issue or submit a pull request! 🐛

Made with ❤️ for the Discord community.
