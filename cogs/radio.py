import discord
from discord import app_commands
from discord.ext import commands
from core.actions import RadioAction
from ui.i18n import t
from ui.utils import respond, get_feedback

class RadioCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.radio = bot.radio

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != self.radio.config.radio_text_channel_id:
            await respond(interaction, get_feedback("wrong_channel_error"), ephemeral=True)
            return False
        return True

    @app_commands.command(name="join", description="Connect the bot to your current voice channel")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await respond(interaction, get_feedback("no_permission"), delete_after=self.radio.config.notification_timeout)
            return
        
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return

        self.radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
        feedback = f"{get_feedback('syncing')} ({interaction.user.voice.channel.name})"
        await respond(interaction, feedback, delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="disconnect", description="Disconnect the bot from voice")
    async def disconnect(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
        self.radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await respond(interaction, get_feedback("severing"), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="volume", description="Adjust bot playback volume (0-100)")
    @app_commands.describe(percent="Volume percentage 0 to 100")
    async def volume(self, interaction: discord.Interaction, percent: int):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
            
        if 0 <= percent <= 100:
            self.radio.dispatch(RadioAction.SET_VOLUME, percent / 100, user=interaction.user)
            feedback = f"{get_feedback('vol_set')} {percent}%"
            await respond(interaction, feedback, delete_after=self.radio.config.notification_timeout)
        else:
            await respond(interaction, get_feedback("vol_range_error"), delete_after=self.radio.config.notification_timeout)

async def setup(bot):
    await bot.add_cog(RadioCog(bot))
