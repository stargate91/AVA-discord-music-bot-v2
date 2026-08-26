import discord
from discord import app_commands
from discord.ext import commands
from core.actions import RadioAction
from ui.i18n import t
from ui.utils import respond, get_feedback
from ui.views.queue import FullQueueView

class QueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.radio = bot.radio

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != self.radio.config.radio_text_channel_id:
            await respond(interaction, get_feedback("wrong_channel_error"), ephemeral=True)
            return False
        return True

    @app_commands.command(name="queue", description="Show the full upcoming song queue")
    async def queue(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
        view = FullQueueView(self.radio, page=0, user=interaction.user)
        await respond(interaction, view=view)

    @app_commands.command(name="loop", description="Toggle single track loop mode")
    async def loop(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
            
        self.radio.dispatch(RadioAction.LOOP, user=interaction.user)
        msg_key = "loop_enabled" if not self.radio.loop_mode else "loop_disabled"
        await respond(interaction, get_feedback(msg_key), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="loopq", description="Toggle full queue loop mode")
    async def loopq(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
            
        self.radio.dispatch(RadioAction.LOOP_QUEUE, user=interaction.user)
        msg_key = "loop_queue_enabled" if not self.radio.loop_queue_mode else "loop_queue_disabled"
        await respond(interaction, get_feedback(msg_key), delete_after=self.radio.config.notification_timeout)

    @app_commands.command(name="shuffle", description="Randomize the upcoming queue order")
    async def shuffle(self, interaction: discord.Interaction):
        if not self.radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=self.radio.config.notification_timeout)
            return
        self.radio.dispatch(RadioAction.SHUFFLE, user=interaction.user)
        await respond(interaction, get_feedback("queue_shuffled"), delete_after=self.radio.config.notification_timeout)

async def setup(bot):
    await bot.add_cog(QueueCog(bot))
