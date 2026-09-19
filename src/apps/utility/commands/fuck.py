__all__ = (
    'FuckCommands',
)

import discord
from discord.ext import commands
from discord import app_commands
from utils.state import State
from utils.commands import command_hook
from utils.enums import Permissions
from utils.modified import ConnectedBot


class FuckCommands(commands.GroupCog, name='fuck'):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot

    @app_commands.command()
    @command_hook(permissions=Permissions.PUBLIC)
    async def ai(self, interaction: discord.Interaction):
        '''Fucks the AI'''
        has_fucked = await State.db.get_fuck_ai(interaction.user.id)
        title = 'You just fucked the AI'
        description = '{} other people have fucked the AI.'
        if has_fucked:
            title = title.replace('just', 'already')
        else:
            await State.db.set_fuck_ai(interaction.user.id)
        total_fucked = await State.db.get_fuck_ai_count()
        description = 'You and ' + description
        description = description.format(total_fucked - 1)
        embed = discord.Embed(
            title=title,
            description=description
        )
        await interaction.response.send_message(embed=embed)