import discord
from discord import app_commands
from discord.ext import commands
from core.actions import RadioAction
from ui.utils import respond, get_feedback

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.radio = bot.radio

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != self.radio.config.radio_text_channel_id:
            await respond(interaction, get_feedback("wrong_channel_error"), ephemeral=True)
            return False
        return True

    @app_commands.command(name="clearcache", description="Clears the local audio cache (Admin only)")
    async def clear_cache(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await respond(interaction, get_feedback("admin_only"), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        count = self.radio.clear_cache()
        await respond(interaction, f"Cache cleared: {count} files removed.", ephemeral=True)

    @app_commands.command(name="restart", description="Restart the bot process (Admin only)")
    async def restart(self, interaction: discord.Interaction):
        if not self.radio.is_admin(interaction.user):
            await respond(interaction, get_feedback("admin_only"), ephemeral=True)
            return
        
        feedback = f"{get_feedback('restarting')}"
        await respond(interaction, feedback, ephemeral=True)
        self.radio.dispatch(RadioAction.RESTART, user=interaction.user)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
