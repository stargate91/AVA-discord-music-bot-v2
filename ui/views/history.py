import discord
from discord.ui import ActionRow, Container, TextDisplay, Separator
from ui.icons import Icons
from ui.theme import Theme
from ui.utils import format_duration, get_feedback
from ui.views.base import handle_ui_error, PaginatedView
from ui.components.list_controls import SearchResultAddButton, FavoriteListButton, ClearHistoryButton
from core.models import Song

class HistoryView(PaginatedView):
    def __init__(self, radio, page: int = 0, user=None):
        history = [Song.from_dict(r) if isinstance(r, dict) else r for r in radio.history]
        super().__init__(radio, history, items_per_page=radio.config.search_items_per_page, page=page)
        self.radio = radio
        self.user = user
        
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {get_feedback('history_label')}"))
        container.add_item(Separator())
        
        if not history:
            container.add_item(TextDisplay(f"*{get_feedback('no_prev_track')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                t_title = truncate(song.title or get_feedback('unknown'), radio.config.list_max_title_len)
                t_user = song.requested_by or get_feedback('unknown')
                t_played = song.played_at or ""
                
                info = f"**{i}. {t_title}** ({format_duration(song.duration)})\n*{t_played} - {t_user}*"
                container.add_item(TextDisplay(info))
                
                row = ActionRow()
                row.add_item(SearchResultAddButton(radio, song))
                row.add_item(FavoriteListButton(radio, song, user_id=self.user.id if self.user else None))
                container.add_item(row)
                
        container.add_item(Separator())
        container.add_item(TextDisplay(self.pagination_info))
        
        nav = ActionRow()
        prev = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary)
        next = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary)
        self.update_pagination_buttons(prev, next)
        
        @handle_ui_error
        async def prev_cb(interaction):
            await interaction.response.defer()
            self.current_page -= 1
            await self.refresh_view(interaction)
        prev.callback = prev_cb

        @handle_ui_error
        async def next_cb(interaction):
            await interaction.response.defer()
            self.current_page += 1
            await self.refresh_view(interaction)
        next.callback = next_cb
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.danger)
        @handle_ui_error
        async def close_cb(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
        close.callback = close_cb

        nav.add_item(prev)
        nav.add_item(next)
        
        if user and radio.is_admin(user):
            nav.add_item(ClearHistoryButton(radio))

        nav.add_item(close)
        container.add_item(nav)
        
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = HistoryView(self.radio, page=self.current_page, user=self.user)
        await interaction.edit_original_response(view=new_view)
