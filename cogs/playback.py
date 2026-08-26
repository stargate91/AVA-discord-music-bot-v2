import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from core.actions import RadioAction, RadioState
from ui.i18n import t
from ui.utils import respond, get_feedback

class PlaybackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.radio = bot.radio

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != self.radio.config.radio_text_channel_id:
            await respond(interaction, get_feedback("wrong_channel_error"), ephemeral=True)
            return False
        return True

    @app_commands.command(name="play", description="Start or resume playback, or add a link/search query")
    @app_commands.describe(url="YouTube/SoundCloud link or search keywords")
    async def play(self, interaction: discord.Interaction, url: Optional[str] = None):
        if not interaction.user.voice:
            await respond(interaction, get_feedback("no_permission"), delete_after=self.radio.config.notification_timeout)
            return

        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return

        if not url:
            if self.radio.status == RadioState.PAUSED:
                self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
                await respond(interaction, get_feedback("resuming_feedback"), delete_after=self.radio.config.notification_timeout)
            else:
                await respond(interaction, get_feedback("nothing_playing"), delete_after=self.radio.config.notification_timeout)
            return
            
        await interaction.response.defer(ephemeral=True)
        url_strip = url.strip()
        
        if self.radio.voice_channel_id is None:
            self.radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
            
        self.radio.dispatch(RadioAction.ADD_EXT_LINK, url_strip, user=interaction.user)
        await respond(interaction, get_feedback("weblink_added"), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return

        if self.radio.status == RadioState.PLAYING:
            self.radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await respond(interaction, get_feedback("pausing"), delete_after=self.radio.config.notification_timeout)
        else:
            await respond(interaction, get_feedback("cannot_pause_stopped"), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="stop", description="Stop playback and clear current track")
    async def stop(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
        self.radio.dispatch(RadioAction.STOP, user=interaction.user)
        await respond(interaction, get_feedback("stopping"), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="skip", description="Skip to the next song in queue")
    async def skip(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
        if not self.radio.queue and not self.radio.future_queue and not self.radio.is_navigating:
            await respond(interaction, get_feedback("no_next_track"), delete_after=self.radio.config.notification_timeout)
            return
        self.radio.dispatch(RadioAction.SKIP, user=interaction.user)
        await respond(interaction, get_feedback("forwarding"), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="back", description="Navigate back to the previous track in history")
    async def back(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
        if not self.radio.history:
            await respond(interaction, get_feedback("no_prev_track"), delete_after=self.radio.config.notification_timeout)
            return
        self.radio.dispatch(RadioAction.BACK, user=interaction.user)
        await respond(interaction, get_feedback("backing"), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="seek", description="Seek to a timestamp (mm:ss or seconds)")
    @app_commands.describe(time="Timestamp e.g. 01:30 or 90")
    async def seek(self, interaction: discord.Interaction, time: str):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return

        if self.radio.status in [RadioState.IDLE, RadioState.STOPPED]:
            await respond(interaction, get_feedback("cannot_seek_stopped"), delete_after=self.radio.config.notification_timeout)
            return
            
        if not self.radio.current_song:
            await respond(interaction, get_feedback("no_current_track"), delete_after=self.radio.config.notification_timeout)
            return
            
        try:
            parts = time.split(":")
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
            else:
                total_seconds = int(time)
        except Exception:
            await respond(interaction, get_feedback("format_error"), delete_after=self.radio.config.notification_timeout)
            return

        self.radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        feedback = f"{get_feedback('jumping')} {time}"
        await respond(interaction, feedback, delete_after=self.radio.config.notification_timeout)

async def setup(bot):
    await bot.add_cog(PlaybackCog(bot))
