import discord
from discord.ui import ActionRow, Container, TextDisplay, Separator
from ui.i18n import t
from ui.icons import Icons
from ui.theme import Theme
from ui.utils import format_duration, get_feedback
from ui.views.base import handle_ui_error, PaginatedView
from ui.components.list_controls import SearchResultAddButton, FavoriteListButton
from core.models import Song

class SearchResultsView(PaginatedView):
    def __init__(self, radio, results, query=None, user=None, page=0):
        results = [Song.from_dict(r) if isinstance(r, dict) else r for r in results]
        super().__init__(radio, results, items_per_page=radio.config.search_items_per_page, page=page)
        self.results = results
        self.query = query
        self.user = user
        
        container = Container(accent_color=Theme.PRIMARY)
        
        header_text = f"### {get_feedback('search_results_title')}"
        if query:
            header_text += f" - *\"{query}\"*"
        if user:
            header_text += f" ({user.name})"
            
        container.add_item(TextDisplay(header_text))
        container.add_item(Separator())
        
        def truncate(text, max_len):
            return (text[:max_len-3] + '...') if len(text) > max_len else text

        items = self.get_page_items()
        for i, res in enumerate(items, self.current_page * self.items_per_page + 1):
            t_title = truncate(res.title or get_feedback('unknown'), radio.config.list_max_title_len)
            info = f"**{i}. {t_title}** ({format_duration(res.duration)})"
            container.add_item(TextDisplay(info))
            
            row = ActionRow()
            row.add_item(SearchResultAddButton(radio, res))
            row.add_item(FavoriteListButton(radio, res, user_id=self.user.id if self.user else None))
            container.add_item(row)
            
        container.add_item(Separator())
        container.add_item(TextDisplay(f"{t('results_label')}: {len(results)} | {self.pagination_info}"))
        
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
        nav.add_item(close)
        container.add_item(nav)
        
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = SearchResultsView(
            self.radio, 
            self.results, 
            query=self.query, 
            user=self.user, 
            page=self.current_page
        )
        await interaction.edit_original_response(view=new_view)
