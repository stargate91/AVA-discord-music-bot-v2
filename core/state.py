import asyncio
import os
import discord
from typing import List, Optional, Any, Callable
from core.actions import RadioState, RadioAction
from core.models import Song
from core.embed_state import EmbedStateManager
from core.database import Database
from services.favorites import FavoriteManager
from services.history import HistoryManager
from services.cache_service import CacheService
from services.permissions import PermissionService
from providers import get_providers, resolve_any, resolve_playlist_any
from utils.logger import log

class RadioManager:
    """
    Central state coordinator and action dispatcher for the Radio Bot.
    Decoupled from direct audio streaming and UI rendering.
    """
    def __init__(self, config, instance_name: str = ""):
        self.config = config
        self.instance_name = instance_name
        self.embed_manager = EmbedStateManager(instance_name=instance_name)
        self.providers = get_providers(config)
        
        # Persistence & Services
        self.db = Database(config.database_path)
        self.fav_manager = FavoriteManager(self.db)
        self.history_manager = HistoryManager(self.db, max_size=config.history_limit)
        self.cache_service = CacheService(config, self.db)
        self.permission_service = PermissionService(config)
        
        # Connection State
        self.voice: Optional[discord.VoiceClient] = None
        self.voice_channel_id: Optional[int] = None
        
        # Playback State
        self.status = RadioState.IDLE
        self.current_song: Optional[Song] = None
        self.queue: List[Song] = []
        self.volume: float = config.default_volume
        self.station_message: Optional[discord.Message] = None
        self.now_playing_message: Optional[discord.Message] = None
        
        # Navigation State (Browser-like History)
        self.future_queue: List[Song] = []
        self.is_navigating: bool = False
        self.history_ptr: int = 0
        
        # UI State
        self.language: str = config.default_language
        self.is_compact: bool = (config.default_ui_mode == "compact")
        self.show_queue: bool = False
        
        # Modes
        self.loop_mode: bool = False
        self.loop_queue_mode: bool = False
        
        # Progress Tracking
        self.track_start_time: Optional[float] = None
        self.track_start_offset: float = 0.0
        self.seek_position: Optional[float] = None
        self.is_seeking: bool = False
        
        # Internal control
        self.action_queue = asyncio.Queue()
        self.last_user: Optional[discord.Member | discord.User] = None
        self.task: Optional[asyncio.Task] = None

        # Callbacks (set by UIManager / Player)
        self.on_state_change: Optional[Callable] = None

    @property
    def history(self) -> List[Song]:
        return self.history_manager.history

    # --- Permission delegates ---
    def is_admin(self, user: discord.Member | discord.User) -> bool:
        return self.permission_service.is_admin(user)

    def can_interact(self, user: discord.Member | discord.User) -> bool:
        return self.permission_service.can_interact(user, self)

    # --- Cache delegates ---
    def is_cached(self, song: Song) -> bool:
        return self.cache_service.is_cached(song)

    def get_cache_path(self, song: Song) -> Optional[str]:
        return self.cache_service.get_cache_path(song)

    async def start_cache_download(self, song: Song):
        await self.cache_service.start_cache_download(song)

    def cleanup_cache(self):
        self.cache_service.cleanup_cache()

    def clear_cache(self) -> int:
        return self.cache_service.clear_cache()

    def delete_cache_file(self, song: Song):
        self.cache_service.delete_cache_file(song)

    def _notify_state_change(self):
        if self.on_state_change:
            if asyncio.iscoroutinefunction(self.on_state_change):
                asyncio.create_task(self.on_state_change(self.current_song))
            else:
                self.on_state_change(self.current_song)

    # --- Action Dispatcher ---
    def dispatch(self, action: RadioAction, data: Any = None, user: Optional[discord.Member | discord.User] = None):
        user_str = f" by {user.name}" if user else " (System/Auto)"
        data_str = f" with [{data}]" if data is not None else ""
        log.info(f"[ACTION] {action.name}{data_str}{user_str}")
        if user:
            self.last_user = user
            
        # 1. Direct handling of state, queue, and database actions
        if self._handle_state_action(action, data, user):
            return

        # 2. Forward audio/voice actions to AudioPlayer
        self.action_queue.put_nowait((action, data))

    def _handle_state_action(self, action: RadioAction, data: Any, user: Optional[discord.Member | discord.User] = None) -> bool:
        """Handles non-audio state, queue, and database actions directly in RadioManager."""
        if action == RadioAction.ADD_EXT_LINK:
            asyncio.create_task(self.add_external_link(data, user=user or self.last_user))
            return True
        elif action == RadioAction.ADD_SONGS:
            asyncio.create_task(self.add_songs(data, user=user or self.last_user))
            return True
        elif action == RadioAction.REMOVE_FROM_QUEUE:
            if data in self.queue:
                self.queue.remove(data)
            self._notify_state_change()
            return True
        elif action == RadioAction.CLEAR_QUEUE:
            self.queue = []
            self._notify_state_change()
            return True
        elif action == RadioAction.MOVE_SONG:
            song, direction = data
            try:
                idx = self.queue.index(song)
                new_idx = idx + direction
                if 0 <= new_idx < len(self.queue):
                    self.queue[idx], self.queue[new_idx] = self.queue[new_idx], self.queue[idx]
                    self._notify_state_change()
            except ValueError:
                pass
            return True
        elif action == RadioAction.TOGGLE_FAVORITE:
            user_id, song = data
            self.fav_manager.toggle_favorite(user_id, song)
            self._notify_state_change()
            return True
        elif action == RadioAction.CLEAR_FAVORITES:
            self.fav_manager.clear_favorites(data)
            self._notify_state_change()
            return True
        elif action == RadioAction.CLEAR_HISTORY:
            self.history_manager.clear()
            self.history_ptr = 0
            self.is_navigating = False
            self._notify_state_change()
            return True
        elif action == RadioAction.CLEAR_CACHE:
            self.clear_cache()
            self._notify_state_change()
            return True
        elif action == RadioAction.LOOP:
            self.loop_mode = not self.loop_mode
            if self.loop_mode:
                self.loop_queue_mode = False
            self._notify_state_change()
            return True
        elif action == RadioAction.LOOP_QUEUE:
            self.loop_queue_mode = not self.loop_queue_mode
            if self.loop_queue_mode:
                self.loop_mode = False
            self._notify_state_change()
            return True
        elif action == RadioAction.SHUFFLE:
            import random
            random.shuffle(self.queue)
            self._notify_state_change()
            return True
            
        return False

    async def add_external_link(self, query: str, user: Optional[discord.Member | discord.User] = None):
        query = query.strip()
        provider = next((p for p in self.providers if p.matches(query)), None)
        
        if provider:
            if provider.is_playlist(query):
                log.info(f"[QUEUE] Playlist detected: {query}")
                asyncio.create_task(self._resolve_playlist_task(query, user))
                return None
            
            cached = self.db.get_cache(query)
            if cached:
                song = Song.from_dict(cached)
                song.path = query
                log.info(f"[CACHE] Hit for: {query}")
                if cached.get("local_path") and os.path.exists(cached["local_path"]):
                    song.is_resolving = False
                else:
                    song.is_resolving = True
            else:
                from ui.i18n import t
                song = Song(
                    title=t("resolving_link"),
                    path=query,
                    uploader="...",
                    duration=0,
                    is_external=True,
                    is_resolving=True
                )
        else:
            log.info(f"[SEARCH] Searching for: {query}")
            search_results = []
            for p in self.providers:
                if hasattr(p, 'search'):
                    res = await p.search(query, limit=1)
                    if res:
                        search_results.extend(res)
            
            if not search_results:
                log.warning(f"[SEARCH] No results found for: {query}")
                return None
            
            data = search_results[0]
            song = Song.from_dict(data)
            song.is_resolving = False
        
        if user:
            song.user_id = str(user.id)
            song.requested_by = user.display_name
            
        self.queue.append(song)
        if not provider:
            log.info(f"[SEARCH] Added first result: {song.title}")
        else:
            log.info(f"[QUEUE] Added link: {query}")
        
        if provider or song.is_resolving:
            asyncio.create_task(self._resolve_link_task(song))
            
        if self.status == RadioState.IDLE and self.voice_channel_id:
            self.status = RadioState.PLAYING
            
        self._notify_state_change()
        return song

    async def add_songs(self, songs: List[Song], user: Optional[discord.Member | discord.User] = None):
        for song in songs:
            if user:
                song.requested_by = user.display_name
                song.user_id = str(user.id)
            self.queue.append(song)
        
        log.info(f"[QUEUE] Added {len(songs)} songs to queue.")
        if self.status == RadioState.IDLE and self.voice_channel_id:
            self.status = RadioState.PLAYING
            
        self._notify_state_change()

    async def _resolve_playlist_task(self, url: str, user: Optional[discord.Member | discord.User] = None):
        tracks_data = await resolve_playlist_any(url, self.providers)
        if tracks_data:
            log.info(f"[RESOLVER] Playlist resolved: {len(tracks_data)} tracks found.")
            for data in tracks_data:
                song = Song.from_dict(data)
                song.is_resolving = False
                if user:
                    song.user_id = str(user.id)
                    song.requested_by = user.display_name
                self.queue.append(song)

            # Atomic bulk cache insertion
            self.db.set_cache_batch(tracks_data)
            
            if self.status == RadioState.IDLE and self.voice_channel_id:
                self.status = RadioState.PLAYING
            self._notify_state_change()
        else:
            log.warning(f"[RESOLVER] Failed to resolve playlist: {url}")

    async def _resolve_link_task(self, song: Song):
        try:
            resolved = await resolve_any(song.path, self.providers)
            if resolved:
                song.update(resolved)
                cached = self.db.get_cache(song.path)
                self.db.set_cache(
                    url=song.path,
                    title=song.title or "",
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or "",
                    local_path=cached.get("local_path") if cached else None
                )
                log.info(f"[RESOLVER] Successfully resolved: {song.uploader} - {song.title}")
            else:
                from ui.i18n import t
                song.title = f"⚠️ {t('error_resolve')} {song.path}"
                log.warning(f"[RESOLVER] Failed to resolve link: {song.path}")
        except Exception as e:
            log.error(f"[RADIO] Resolution task exception: {e}")
        finally:
            song.is_resolving = False
            song.resolve_event.set()
            self._notify_state_change()
