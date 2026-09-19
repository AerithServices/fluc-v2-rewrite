import aiohttp
import os
import discord
import utils
from urllib import parse
from utils.enums import PullStatus
from utils.models import Auth
from utils.state import State
from discord import ui
from typing import Optional

class RejoinView(ui.View):
    def __init__(self, author_id: Optional[int]):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.disabled = author_id is None
        button = ui.Button(
            label='Rejoin Now',
            disabled=self.disabled,
            custom_id='rejoin_button'
        )
        button.callback = self.button_callback
        self.embed = discord.Embed(
            title='Notice',
            description='Seems like you have left the main server.\nYou cannot use the bot unless you rejoin.'
        )
        self.button = button
        self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        if self.disabled:
            self.button.disabled = True
            await interaction.response.edit_message(embed=self.embed, view=self)
            return
        self.disabled = True
        user = await State.db.get_user(interaction.user.id)
        if not user:
            return
        main_server = State.verify_config.main_server
        status = await utils.pull_user(user, main_server)
        if not status is PullStatus.PULLED:
            # User not authed
            await interaction.response.send_message('Join via discord.gg/fluc', ephemeral=True)
            return
        if status is PullStatus.PULLED:
            await interaction.response.send_message('The user has been added back to main server.', ephemeral=True)