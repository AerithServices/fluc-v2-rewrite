__all__ = (
    'GuildContext',
    'ConnectedBot',
    'EventCog',
    'GuildInteraction'
)

import discord
import aiohttp
from discord.ext import commands
from typing import Optional
from abc import ABCMeta

class GuildInteraction(discord.Interaction):
    user: discord.Member # pyright: ignore[reportIncompatibleVariableOverride]
    @property
    def guild(self) -> discord.Guild:
        """:class:`discord.Guild`: The guild the interaction was sent from."""
        # The user.guild attribute is set in __init__ to the fallback guild if available
        # Therefore, we can use that instead of recreating it every time this property is
        # accessed
        return self._state._get_guild(self.guild_id) or getattr(self.user, 'guild', None) # pyright: ignore[reportReturnType]

class GuildContext(commands.Context):
    @discord.utils.cached_property
    def author(self) -> discord.Member:
        """:class:`.Member`:
        Returns the author associated with this context's command. Shorthand for :attr:`.Message.author`
        """
        # Author is always discord.Member if command was ran in a server
        return self.message.author # pyright: ignore[reportReturnType]

    @discord.utils.cached_property
    def guild(self) -> discord.Guild:
        """:class:`discord.Guild`: Returns the guild associated with this context's command."""
        # Can't be none if command ran in a server
        return self.message.guild # pyright: ignore[reportReturnType]
    

class ConnectedBot(commands.Bot):
    _session: Optional[aiohttp.ClientSession]

    def __init__(self, bot: commands.Bot):
        self = bot

    @property
    def user(self) -> discord.ClientUser:
        """:class:`discord.ClientUser`: Represents the connected client."""
        return self._connection.user # pyright: ignore[reportReturnType]
    
    @property
    def session(self) -> aiohttp.ClientSession:
        '''Returns session of the bot.'''
        return NotImplemented
    

class CogABCMeta(commands.CogMeta, ABCMeta):
    pass


class EventCog(commands.Cog, metaclass=CogABCMeta):
    bot: ConnectedBot