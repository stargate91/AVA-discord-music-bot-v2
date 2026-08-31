import asyncio
import random
import discord
from ui.i18n import t, init_translate
from core.actions import RadioState
from core.models import Song
from ui.views.player import WelcomeLayout, FrequencyStationView, NowPlayingView
from ui.context import UIContext
from ui.utils import safe_delete_message, safe_fetch_message
from utils.logger import log

class UIManager:
    def __init__(self, bot: discord.Client, config, radio):
        self.bot = bot
        self.config = config
        self.radio = radio
        self._ui_lock = asyncio.Lock()
        self._last_cleanup = 0.0
        self._last_presence_sig = None
        
        # Initialize UI context object for dependency injection
        self.context = UIContext(
            bot=self.bot,
            config=self.config,
            update_callback=self.update_now_playing
        )
        
        # Initialize sub-systems
        init_translate(radio)

    async def update_now_playing(self, song: Song | None, force_channel_id: int | None = None, force_cleanup: bool = False):
        """Public entry point for UI updates with locking."""
        async with self._ui_lock:
            await self._update_ui_internal(song, force_channel_id=force_channel_id, force_cleanup=force_cleanup)

    async def _update_ui_internal(self, song: Song | None, force_channel_id: int | None = None, force_cleanup: bool = False):
        """Internal UI rendering logic."""
        try:
            if isinstance(song, dict):
                song = None
                
            has_no_song = song is None or not song.path
            show_player = bool(not has_no_song or self.radio.voice_channel_id)
            
            if not self.bot or self.bot.is_closed():
                return
            
            # 1. Presence & Channel Status Updates (with deduplication)
            await self._update_presence(song)
            await self._update_channel_status(song, force_channel_id=force_channel_id)

            channel = self.bot.get_channel(self.config.radio_text_channel_id)
            if not channel:
                try: 
                    channel = await self.bot.fetch_channel(self.config.radio_text_channel_id)
                except Exception as e:
                    log.error(f"UI Manager could not find radio channel {self.config.radio_text_channel_id}: {e}")
                    return

            # 2. Handle Station Message (Header)
            await self._render_station_message(channel)

            # 3. Handle Player Message (Centerpiece)
            await self._render_player_message(channel, song, show_player)

            # 4. Aggressive Cleanup
            await asyncio.sleep(0.5) 
            await self._cleanup_stray_messages(channel, force=force_cleanup or not show_player)

        except Exception as e:
            log.error(f"UIManager update failed: {e}")

    async def _update_presence(self, song: Song | None):
        try:
            if self.radio.status == RadioState.PLAYING and song:
                current_sig = f"PLAYING:{song.title}"
                if current_sig != self._last_presence_sig:
                    activity = discord.Activity(
                        type=discord.ActivityType.listening,
                        name=song.title or t('unknown')
                    )
                    await self.bot.change_presence(activity=activity)
                    self._last_presence_sig = current_sig
            else:
                if self.radio.status == RadioState.PAUSED:
                    msg_src = t('holding_rhythm')
                elif self.radio.status == RadioState.IDLE:
                    msg_src = t('waiting_melody')
                else:
                    msg_src = t('at_command')
                
                final_msg = random.choice(msg_src) if isinstance(msg_src, list) else msg_src
                current_sig = f"{self.radio.status.name}:{final_msg}"
                if current_sig != self._last_presence_sig:
                    await self.bot.change_presence(activity=discord.Game(name=final_msg))
                    self._last_presence_sig = current_sig
        except Exception as e:
            log.debug(f"Presence update failed: {e}")

    async def _update_channel_status(self, song: Song | None, force_channel_id: int | None = None):
        """Updates the Voice Channel's status text (if enabled)."""
        if not self.config.update_voice_status:
            return
            
        try:
            target_id = force_channel_id or self.radio.voice_channel_id
            if not target_id:
                return
                
            channel = self.bot.get_channel(target_id)
            if not channel:
                channel = await self.bot.fetch_channel(target_id)
                
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return

            if self.radio.status == RadioState.PLAYING and song:
                status_text = t('channel_status_playing', TITLE=song.title)
            else:
                status_text = None

            current_status = getattr(channel, 'status', 'UNKNOWN_ATTR')
            if current_status == 'UNKNOWN_ATTR' or current_status != status_text:
                await channel.edit(status=status_text)
                
        except Exception as e:
            log.debug(f"Voice channel status update failed: {e}")

    async def _cleanup_stray_messages(self, channel, force=False):
        now = asyncio.get_event_loop().time()
        if not force and (now - self._last_cleanup < self.config.ui_cleanup_frequency):
            return 
        self._last_cleanup = now

        try:
            current_station_id = self.radio.station_message.id if self.radio.station_message else None
            current_player_id = self.radio.now_playing_message.id if self.radio.now_playing_message else None
            current_search_id = self.radio.embed_manager.load_message_id("search")
            
            known_ids = {current_station_id, current_player_id, current_search_id}
            known_ids = {id for id in known_ids if id is not None}
            
            log.debug(f"[UI] Cleaning up. Known IDs: {known_ids}")
            
            to_delete = []
            async for msg in channel.history(limit=self.config.message_cleanup_limit):
                if msg.author.id == self.bot.user.id and msg.id not in known_ids:
                    to_delete.append(msg)
            
            if to_delete:
                if len(to_delete) > 1:
                    try:
                        await channel.delete_messages(to_delete)
                    except Exception:
                        for msg in to_delete:
                            await safe_delete_message(msg)
                else:
                    await safe_delete_message(to_delete[0])
        except Exception as ex:
            log.warning(f"UI Cleanup sweep failed: {ex}")

    async def _render_station_message(self, channel):
        if not self.radio.voice_channel_id:
            view = WelcomeLayout(self.radio, context=self.context)
        else:
            view = FrequencyStationView(self.radio, context=self.context)
            
        if not self.radio.station_message:
            msg_id = self.radio.embed_manager.load_message_id("station")
            if msg_id:
                fetched = await safe_fetch_message(channel, msg_id)
                if fetched and fetched.author.id == self.bot.user.id:
                    self.radio.station_message = fetched
                else:
                    self.radio.station_message = None
            
        if self.radio.station_message:
            try: 
                await self.radio.station_message.edit(view=view)
            except Exception: 
                self.radio.station_message = await channel.send(view=view)
        else:
            self.radio.station_message = await channel.send(view=view)
        
        self.radio.embed_manager.save_message_id("station", self.radio.station_message.id)

    async def _render_player_message(self, channel, song, show_player):
        if not channel:
            return
        
        if not show_player:
            msg_id = self.radio.embed_manager.load_message_id("player")
            if self.radio.now_playing_message:
                if self.radio.now_playing_message.author.id == self.bot.user.id:
                    await safe_delete_message(self.radio.now_playing_message)
                self.radio.now_playing_message = None
            elif msg_id:
                m = await safe_fetch_message(channel, msg_id)
                if m and m.author.id == self.bot.user.id:
                    await safe_delete_message(m)
            
            self.radio.embed_manager.save_message_id("player", None)
            return

        player_view = NowPlayingView(self.radio, song=song, context=self.context)
        
        if not self.radio.now_playing_message:
            msg_id = self.radio.embed_manager.load_message_id("player")
            if msg_id:
                fetched = await safe_fetch_message(channel, msg_id)
                if fetched and fetched.author.id == self.bot.user.id:
                    self.radio.now_playing_message = fetched
                else:
                    self.radio.now_playing_message = None
            
        if self.radio.now_playing_message:
            try:
                await self.radio.now_playing_message.edit(embed=None, view=player_view)
            except Exception:
                self.radio.now_playing_message = await channel.send(view=player_view)
        else:
            self.radio.now_playing_message = await channel.send(view=player_view)
            
        self.radio.embed_manager.save_message_id("player", self.radio.now_playing_message.id)

    async def force_new_embed(self):
        """Immediately clears message IDs and triggers a fresh UI build."""
        async with self._ui_lock:
            self.radio.now_playing_message = None
            self.radio.station_message = None
            
            self.radio.embed_manager.save_message_id("player", None)
            self.radio.embed_manager.save_message_id("station", None)
            self.radio.embed_manager.save_message_id("search", None)
            
            await self._update_ui_internal(self.radio.current_song, force_cleanup=True)

    async def refresh_all_uis(self):
        """Triggers a lock-safe update of the current UI state."""
        await self.update_now_playing(self.radio.current_song)

    async def clear_voice_status(self, channel_id: int):
        """Public method to clear the status of a specific voice channel."""
        async with self._ui_lock:
            await self._update_channel_status(None, force_channel_id=channel_id)
