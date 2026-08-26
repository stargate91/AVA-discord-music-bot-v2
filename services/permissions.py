import discord
from core.actions import RadioState

class PermissionService:
    def __init__(self, config):
        self.config = config

    def is_admin(self, user: discord.Member | discord.User) -> bool:
        if not isinstance(user, discord.Member):
            return False
        
        if user.guild_permissions.administrator:
            return True

        if user.id == user.guild.owner_id:
            return True

        user_role_ids = [role.id for role in user.roles]
        if self.config.admin_role_id > 0 and self.config.admin_role_id in user_role_ids:
            return True
        if self.config.sysadmin_role_id > 0 and self.config.sysadmin_role_id in user_role_ids:
            return True
        
        return False

    def can_interact(self, user: discord.Member | discord.User, radio) -> bool:
        """
        Checks if the user has permission to interact with the bot.
        Admins can always interact.
        The voice channel restriction ONLY applies if the bot is:
        - PLAYING
        - PAUSED
        - STOPPED
        If the bot is IDLE, anyone can interact (e.g. to make it join their channel).
        """
        if self.is_admin(user):
            return True

        # If IDLE, we don't restrict by channel
        if radio.status == RadioState.IDLE:
            return True

        if not radio.voice or not radio.voice.channel:
            # If not in voice despite status, allow interaction
            return True

        if not isinstance(user, discord.Member):
            return False

        # Must be in the same voice channel if the bot is active
        if not user.voice or user.voice.channel.id != radio.voice.channel.id:
            return False

        return True
