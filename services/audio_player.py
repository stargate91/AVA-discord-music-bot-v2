import os
import time
import asyncio
import discord
from typing import Optional, Callable, TYPE_CHECKING
from core.actions import RadioAction, RadioState
from core.models import Song
from utils.logger import log

if TYPE_CHECKING:
    from core.state import RadioManager

class RadioPlayer:
    def __init__(self, bot: discord.Client, config, radio: 'RadioManager', 
                 update_ui_callback: Callable, refresh_ui_callback: Callable, 
                 cleanup_ui_callback: Optional[Callable] = None):
        self.bot = bot
        self.config = config
        self.radio = radio
        self.update_ui = update_ui_callback
        self.refresh_ui = refresh_ui_callback
        self.cleanup_ui = cleanup_ui_callback
        
        self.solitary_timeout = self.config.solitary_timeout_seconds
        self.solitary_start = None
        self._voice_lock = asyncio.Lock()
        self.last_cache_cleanup = 0.0
        
        self.prefetched_song: Optional[Song] = None
        self.prefetch_task: Optional[asyncio.Task] = None
        
        self.radio.on_state_change = self.update_ui

    async def ensure_voice(self) -> Optional[discord.VoiceClient]:
        """Ensures the bot is connected to the correct voice channel."""
        async with self._voice_lock:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild or not self.radio.voice_channel_id:
                return None
                
            channel = guild.get_channel(self.radio.voice_channel_id)
            if not channel:
                log.warning(f"[VOICE] Target channel {self.radio.voice_channel_id} not found in guild {guild.name}")
                return None

            if guild.voice_client:
                if guild.voice_client.is_connected():
                    self.radio.voice = guild.voice_client
                    if self.radio.voice.channel.id != channel.id:
                        log.info(f"[VOICE] Moving from {self.radio.voice.channel.name} to {channel.name}")
                        await self.radio.voice.move_to(channel)
                    return self.radio.voice
                else:
                    log.warning(f"[VOICE] Dead voice client found for guild {guild.name}. Cleaning up.")
                    try:
                        await guild.voice_client.disconnect(force=True)
                    except Exception:
                        pass
                    self.radio.voice = None

            # Check for forbidden bots
            for member in channel.members:
                if member.bot and member.id in self.config.forbidden_bot_ids:
                    log.warning(f"[VOICE] Forbidden bot {member.name} ({member.id}) detected in {channel.name}. Aborting join.")
                    return None
            
            try:
                log.info(f"[VOICE] Connecting to {channel.name} in guild {guild.name}...")
                self.radio.voice = await channel.connect(reconnect=True, timeout=30.0, self_deaf=True)
                log.info(f"[VOICE] Successfully connected to {channel.name}")
            except Exception as e:
                log.warning(f"[VOICE] Connection attempt failed: {type(e).__name__}: {e}")
                self.radio.voice = None
                return None

            return self.radio.voice

    async def run_loop(self):
        """Main player lifecycle loop."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                voice = await self.ensure_voice()
                
                # 1. State: DISCONNECTED
                if not voice:
                    await self._handle_disconnected_state()
                    continue

                # 2. Monitor Solitary Status
                if await self._check_solitary_timeout(voice):
                    continue

                # 3. State: IDLE, STOPPED, or PAUSED
                if self.radio.status in [RadioState.IDLE, RadioState.STOPPED, RadioState.PAUSED]:
                    if await self._handle_idle_state(voice):
                        continue

                # 4. State: PLAYING (Song Selection & Start)
                if self.radio.status == RadioState.PLAYING:
                    await self._start_playback(voice)
                
                # 5. Periodic cache cleanup
                if time.time() - self.last_cache_cleanup > 3600:
                    self.radio.cleanup_cache()
                    self.last_cache_cleanup = time.time()

                # 6. Safety sleep to prevent busy-waiting
                await asyncio.sleep(self.config.player_loop_sleep)

            except Exception as e:
                import traceback
                log.error(f"Player crash: {e}")
                log.error(traceback.format_exc())
                await asyncio.sleep(self.config.error_retry_seconds)

    async def _handle_disconnected_state(self):
        """Logic when voice is not connected."""
        self.solitary_start = None
        try:
            action, data = await asyncio.wait_for(self.radio.action_queue.get(), timeout=self.config.action_timeout)
            if action == RadioAction.JOIN:
                self.radio.voice_channel_id = data
                self.radio.status = RadioState.PLAYING
            elif action == RadioAction.DISCONNECT:
                await self._disconnect(None)
            elif action == RadioAction.RESTART:
                await self._handle_restart()
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            log.error(f"[PLAYER] Error in disconnected state handler: {e}")

    async def _check_solitary_timeout(self, voice) -> bool:
        """Returns True if the bot disconnected due to being alone."""
        real_members = [m for m in voice.channel.members if not m.bot]
        if len(real_members) == 0:
            if self.solitary_start is None:
                log.info(f"[SOLITARY] Bot is alone. Starting {self.solitary_timeout}s countdown.")
                self.solitary_start = asyncio.get_event_loop().time()
            elif asyncio.get_event_loop().time() - self.solitary_start >= self.solitary_timeout:
                log.info(f"Auto-disconnecting: Bot was alone for {self.solitary_timeout}s.")
                self.solitary_start = None
                await self._disconnect(voice)
                return True
        else:
            if self.solitary_start is not None:
                log.info("[SOLITARY] Member joined or present. Resetting countdown.")
            self.solitary_start = None
        return False

    async def _handle_idle_state(self, voice) -> bool:
        """Logic when voice is connected but nothing is playing."""
        try:
            action, data = await asyncio.wait_for(self.radio.action_queue.get(), timeout=self.config.action_timeout)
            self.solitary_start = None
            
            if action == RadioAction.SET_VOLUME:
                self.radio.volume = data
                return True
            elif action == RadioAction.DISCONNECT:
                await self._disconnect(voice)
                return True
            elif action == RadioAction.REPLAY:
                if self.radio.status == RadioState.STOPPED and self.radio.current_song:
                    self.radio.is_seeking = True
                    self.radio.seek_position = 0
                elif self.radio.status == RadioState.PAUSED and self.radio.current_song:
                    self.radio.is_seeking = True
                    self.radio.seek_position = None
            elif action == RadioAction.SKIP:
                if self.radio.future_queue or self.radio.queue:
                    self.radio.status = RadioState.PLAYING
                    return False
                return True
            elif action == RadioAction.BACK:
                next_ptr = self.radio.history_ptr + (1 if self.radio.current_song else 0)
                back_song = self.radio.history_manager.get_latest(offset=next_ptr)
                if back_song:
                    if self.radio.current_song:
                        self.radio.future_queue.insert(0, self.radio.current_song)
                    self.radio.current_song = back_song
                    self.radio.history_ptr = next_ptr
                    self.radio.is_navigating = True
                    self.radio.is_seeking = True
                    self.radio.status = RadioState.PLAYING
                    return False
                return True
            elif action == RadioAction.SEEK:
                log.info(f"[PLAYER] Idle Seeking to: {data}s")
                self.radio.seek_position = data
                self.radio.track_start_offset = data
                self.radio.is_seeking = True
                await self.update_ui(self.radio.current_song)
                return True
            elif action == RadioAction.RESTART:
                await self._handle_restart()
                return True
            else: 
                return True
            
            self.radio.status = RadioState.PLAYING
            return False
        except asyncio.TimeoutError:
            return True

    async def _disconnect(self, voice):
        self.radio.voice_channel_id = None
        self.radio.status = RadioState.IDLE
        self.radio.current_song = None
        self.prefetched_song = None
        if voice:
            await voice.disconnect()
        if self.cleanup_ui:
            await self.cleanup_ui()
        self.solitary_start = None

    async def _handle_restart(self):
        log.info("[PLAYER] Restart triggered. Closing bot connection...")
        os.environ["BOT_RESTART"] = "1"
        await self.bot.close()

    async def _start_playback(self, voice):
        """Prepares and starts audio playback."""
        self.prefetched_song = None
        
        if not self.radio.current_song or not self.radio.is_seeking:
            if self.radio.loop_mode and self.radio.current_song and not self.radio.is_navigating:
                log.info(f"[PLAYER] Loop Mode active. Replaying: {self.radio.current_song.title}")
                self.radio.is_seeking = True
                self.radio.seek_position = 0
            elif self.radio.future_queue:
                self.radio.current_song = self.radio.future_queue.pop(0)
                self.radio.is_navigating = True
                self.radio.history_ptr -= 1
            elif self.radio.queue:
                if self.radio.loop_queue_mode and self.radio.current_song and not self.radio.is_navigating:
                    self.radio.queue.append(self.radio.current_song)
                
                self.radio.current_song = self.radio.queue.pop(0)
                self.radio.is_navigating = False
                self.radio.history_ptr = 0
            else:
                if self.radio.loop_queue_mode and self.radio.current_song and not self.radio.is_navigating:
                    self.radio.current_song = self.radio.queue.pop(0)
                else:
                    if voice and voice.is_playing():
                        log.warning("[PLAYER] Queue empty but voice still playing. Delaying IDLE state.")
                        await asyncio.sleep(1.0)
                        return

                    self.radio.status = RadioState.IDLE
                    self.radio.current_song = None
                    self.radio.is_navigating = False
                    self.radio.history_ptr = 0
                    await self.update_ui(None)
                    return
        
        song = self.radio.current_song
        self.radio.status = RadioState.BUFFERING
        await self.update_ui(song)
        
        if self.radio.is_seeking and song and song.is_external:
            log.info(f"[PLAYER] Re-resolving stream for: {song.title}")
            song.stream_url = None
            
        self.radio.is_seeking = False
        
        if self.radio.is_cached(song):
            source_path = self.radio.get_cache_path(song)
            log.info(f"[CACHE] Using local file for: {song.title}")
        else:
            source_path = await self._resolve_source(song)
            if song.is_external:
                await self.radio.start_cache_download(song)
                
        if not source_path:
            log.error(f"[PLAYER] Could not resolve playable audio source for: {song.title if song else 'Unknown'}")
            self.radio.current_song = None
            self.radio.status = RadioState.IDLE
            await self.update_ui(None)
            return

        self.history_recorded = False
        self.playback_start_time = asyncio.get_event_loop().time()

        self.radio.track_start_offset = self.radio.seek_position or 0.0
        self.radio.seek_position = None
        
        done = asyncio.Event()
        def after_playing(error):
            if error:
                err_msg = str(error)
                if "read of closed file" not in err_msg.lower():
                    log.error(f"[PLAYER] Playback error: {error}")
                else:
                    log.debug(f"[PLAYER] Suppressed noise: {err_msg}")
            self.bot.loop.call_soon_threadsafe(done.set)

        if voice.is_playing() or voice.is_paused():
            voice.stop()
            await asyncio.sleep(0.05)
        
        self.radio.track_start_time = asyncio.get_event_loop().time()
        self.radio.status = RadioState.PLAYING
        
        audio_source = self._create_ffmpeg_source(source_path, song)
        
        voice.play(audio_source, after=after_playing)
        log.info(f"[PLAYER] Started playing: {song.uploader} - {song.title} ({song.duration}s)")
        await self.update_ui(song)

        await self._playback_monitor_loop(voice, song, done)
        
        try:
            await asyncio.wait_for(done.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            log.warning(f"[PLAYER] Playback thread for \"{song.title}\" did not exit within 3s. Forcing cleanup.")

        if not done.is_set(): 
            log.info(f"[PLAYER] Monitor loop broke or timed out: {song.title}")
        else:
            log.info(f"[PLAYER] Track finished normally: {song.title}")

        if not self.radio.is_seeking:
            self.radio.track_start_offset = 0.0
            if self.config.ephemeral_cache:
                self.radio.delete_cache_file(song)
        self.radio.track_start_time = None
        audio_source.cleanup()

    async def _prefetch_next_track(self, song: Song):
        """Pre-resolves stream URL and/or downloads audio for the upcoming track in background."""
        if not song or self.radio.is_cached(song):
            return
            
        try:
            log.info(f"[PREFETCH] Pre-buffering next track: {song.title or song.path}")
            if song.is_external and not song.stream_url and not song.is_resolving:
                from providers import resolve_any
                resolved = await resolve_any(song.path, self.radio.providers)
                if resolved:
                    song.update(resolved)
                    self.radio.db.set_cache(
                        url=song.path,
                        title=song.title or "",
                        uploader=song.uploader or "Unknown",
                        duration=song.duration,
                        thumbnail_url=song.thumbnail_url or ""
                    )
                    log.info(f"[PREFETCH] Stream URL resolved ahead of time for: {song.title}")
            
            if song.is_external and not self.radio.is_cached(song):
                await self.radio.start_cache_download(song)
        except Exception as e:
            log.warning(f"[PREFETCH] Error pre-buffering {song.title or song.path}: {e}")

    async def _resolve_source(self, song: Song) -> Optional[str]:
        if os.path.exists(song.path):
            return song.path

        if self.radio.is_cached(song):
            return self.radio.get_cache_path(song)

        if song.stream_url and not song.is_resolving:
            log.info(f"[PLAYER] Using pre-buffered stream URL for: {song.title}")
            return song.stream_url

        if song.is_resolving:
            log.info(f"[PLAYER] Waiting for background resolution: {song.title}")
            try:
                await asyncio.wait_for(song.resolve_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                log.warning(f"[PLAYER] Resolution timed out for: {song.title}")

        if self.radio.is_cached(song):
            return self.radio.get_cache_path(song)

        source_path = song.path
        if song.is_external:
            if not song.stream_url or song.is_resolving:
                await self.update_ui(song)
                from providers import resolve_any
                resolved = await resolve_any(source_path, self.radio.providers)
                if resolved:
                    song.update(resolved)
                    self.radio.db.set_cache(
                        url=source_path,
                        title=song.title or "",
                        uploader=song.uploader or "Unknown",
                        duration=song.duration,
                        thumbnail_url=song.thumbnail_url or ""
                    )
            
            if song.stream_url:
                return song.stream_url
            return None
        return source_path

    def _create_ffmpeg_source(self, source_path: str, song: Optional[Song] = None):
        is_url = source_path.startswith("http")
        reconnect_opts = self.config.ffmpeg_reconnect_options if is_url else ""
        user_agent = self.config.user_agent if is_url else ""
        
        before_opts_list = ["-nostdin"]
        if self.radio.track_start_offset > 0:
            before_opts_list.append(f"-ss {self.radio.track_start_offset}")
             
        if is_url:
            ua = None
            if song and song.http_headers and "User-Agent" in song.http_headers:
                ua = song.http_headers["User-Agent"]
            elif user_agent:
                ua = user_agent

            if ua:
                before_opts_list.append(f"-user_agent \"{ua}\"")
            if reconnect_opts:
                before_opts_list.append(reconnect_opts)
            
            is_soundcloud = "soundcloud.com" in source_path or (song and song.webpage_url and "soundcloud.com" in song.webpage_url)
            if is_soundcloud:
                before_opts_list.append("-headers \"Referer: https://soundcloud.com/\"")
                before_opts_list.append("-allowed_extensions ALL")
                
            before_opts_list.extend(["-analyzeduration 0", "-probesize 32k"])
        
        before_opts = " ".join(before_opts_list)
        filter_chain = f"volume={self.radio.volume}"
        options = f'-vn -filter:a "{filter_chain}" -c:a libopus -b:a {self.config.audio_bitrate} -ar 48000 -ac 2 -f opus -threads 2'
        
        return discord.FFmpegOpusAudio(
            source_path,
            executable=self.config.ffmpeg_path,
            before_options=before_opts,
            options=options
        )

    async def _playback_monitor_loop(self, voice, song, done):
        """Listens for actions while a track is playing and triggers pre-buffering."""
        while not done.is_set():
            try:
                if await self._check_solitary_timeout(voice):
                    break
                
                # Delayed History Recording
                if not self.history_recorded and not self.radio.is_navigating and song:
                    elapsed_total = self.radio.track_start_offset
                    if self.radio.track_start_time:
                        elapsed_total += (asyncio.get_event_loop().time() - self.radio.track_start_time)
                    threshold = min(15.0, (song.duration * 0.1) if song.duration > 0 else 15.0)
                    if elapsed_total >= threshold:
                        log.info(f"[HISTORY] Recording track after threshold: {song.title}")
                        self.radio.history_manager.add(song)
                        self.history_recorded = True

                # Gapless Pre-buffering trigger
                if song and not self.prefetched_song and (self.radio.future_queue or self.radio.queue):
                    elapsed_current = self.radio.track_start_offset
                    if self.radio.track_start_time:
                        elapsed_current += (asyncio.get_event_loop().time() - self.radio.track_start_time)
                    
                    remaining = (song.duration - elapsed_current) if song.duration > 0 else 0
                    if song.duration == 0 or remaining <= 25.0 or elapsed_current >= 10.0:
                        next_song = self.radio.future_queue[0] if self.radio.future_queue else self.radio.queue[0]
                        if next_song and next_song != song:
                            self.prefetched_song = next_song
                            self.prefetch_task = asyncio.create_task(self._prefetch_next_track(next_song))

                action_task = asyncio.create_task(self.radio.action_queue.get())
                done_task = asyncio.create_task(done.wait())
                
                finished, pending = await asyncio.wait(
                    [action_task, done_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self.config.action_timeout
                )
                for task in pending:
                    task.cancel()

                if action_task in finished:
                    action, data = action_task.result()
                    if await self._handle_playback_action(voice, action, data, song):
                        break
                
                if done_task in finished:
                    break
            except asyncio.TimeoutError:
                continue

    async def _handle_playback_action(self, voice, action, data, song) -> bool:
        self.solitary_start = None
        if action == RadioAction.SKIP:
            log.info("[PLAYER] Skipping current track.")
            self.radio.is_navigating = True
            self.radio.is_seeking = False
            voice.stop()
            return True
        elif action == RadioAction.SEEK:
            log.info(f"[PLAYER] Seeking to: {data}s")
            self.radio.seek_position = data
            self.radio.is_seeking = True
            if self.radio.status == RadioState.PAUSED:
                self.radio.track_start_offset = data
            voice.stop()
            if self.radio.status == RadioState.PAUSED:
                await self.update_ui(song)
            return True
        elif action == RadioAction.SET_VOLUME:
            log.info(f"[PLAYER] Volume changed to: {int(data*100)}%")
            self.radio.volume = data
            if self.radio.track_start_time:
                elapsed = (asyncio.get_event_loop().time() - self.radio.track_start_time)
                self.radio.seek_position = self.radio.track_start_offset + elapsed
            else:
                self.radio.seek_position = self.radio.track_start_offset
            self.radio.is_seeking = True
            voice.stop()
            return True
        elif action == RadioAction.PAUSE:
            if voice.is_playing():
                log.info("[PLAYER] Pausing playback.")
                voice.pause()
                if self.radio.track_start_time:
                    self.radio.track_start_offset += (asyncio.get_event_loop().time() - self.radio.track_start_time)
                self.radio.track_start_time = None
                self.radio.status = RadioState.PAUSED
                await self.update_ui(song)
            return False
        elif action == RadioAction.REPLAY:
            if self.radio.status == RadioState.PAUSED:
                log.info("[PLAYER] Resuming playback.")
                voice.resume()
                self.radio.track_start_time = asyncio.get_event_loop().time()
                self.radio.status = RadioState.PLAYING
                await self.update_ui(song)
                return False
            else:
                log.info("[PLAYER] Replaying track from start.")
                self.radio.seek_position = 0
                self.radio.is_seeking = True
                voice.stop()
                return True
        elif action == RadioAction.BACK:
            elapsed = self.radio.track_start_offset
            if self.radio.track_start_time and self.radio.status == RadioState.PLAYING:
                elapsed += (asyncio.get_event_loop().time() - self.radio.track_start_time)
            
            if elapsed > 10.0:
                log.info(f"[PLAYER] Restarting current track (elapsed: {int(elapsed)}s)")
                self.radio.seek_position = 0
                self.radio.is_seeking = True
                voice.stop()
                return True

            log.info(f"[PLAYER] Navigating to previous track in history (elapsed: {int(elapsed)}s)")
            next_ptr = self.radio.history_ptr + (1 if self.radio.is_navigating else 0)
            back_song = self.radio.history_manager.get_latest(offset=next_ptr)

            if back_song:
                if self.radio.current_song:
                    self.radio.future_queue.insert(0, self.radio.current_song)
                self.radio.current_song = back_song
                self.radio.history_ptr = next_ptr
                self.radio.is_navigating = True
                self.radio.is_seeking = True
                voice.stop()
                return True
            
            self.radio.seek_position = 0
            self.radio.is_seeking = True
            voice.stop()
            return True
        elif action == RadioAction.STOP:
            log.info("[PLAYER] Stopping playback.")
            self.radio.status = RadioState.STOPPED
            self.radio.track_start_offset = 0.0
            self.radio.track_start_time = None
            voice.stop()
            await self.update_ui(song)
            return True
        elif action == RadioAction.DISCONNECT:
            await self._disconnect(voice)
            return True
        elif action == RadioAction.RESTART:
            await self._handle_restart()
            return True
        return False
