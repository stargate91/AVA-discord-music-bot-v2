import discord
from discord.ui import Modal, TextInput
from ui.icons import Icons
from ui.i18n import t
from ui.utils import respond, get_feedback
from ui.views.base import handle_ui_error
from core.actions import RadioAction

class VolumeButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('vol_label'),
            emoji=Icons.VOLUME,
            style=discord.ButtonStyle.secondary,
            custom_id="volume_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        modal = VolumeModal(self.radio)
        await interaction.response.send_modal(modal)

class VolumeModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("vol_modal_title"))
        self.radio = radio
        self.volume_input = TextInput(
            label=t("vol_input_label"),
            placeholder="50",
            style=discord.TextStyle.short,
            required=True,
            max_length=3
        )
        self.add_item(self.volume_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.volume_input.value)
            if 0 <= value <= 100:
                self.radio.dispatch(RadioAction.SET_VOLUME, value / 100, user=interaction.user)
                feedback = f"{get_feedback('vol_set')} {value}%"
                await respond(interaction, feedback, delete_after=self.radio.config.notification_timeout)
            else:
                await respond(interaction, get_feedback("vol_range_error"), delete_after=self.radio.config.notification_timeout)
        except Exception:
            await respond(interaction, get_feedback("invalid_number"), delete_after=self.radio.config.notification_timeout)
