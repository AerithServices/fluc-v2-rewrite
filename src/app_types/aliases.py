__all__ = (
    'TCoro',
    'TCommand',
    'TGuildChannel'
)

import discord
from typing import Callable, Coroutine, Any, TypeVar, ParamSpec, Union

T = TypeVar('T')
P = ParamSpec('P')

TCoro = Coroutine[Any, Any, T]
TCommand = Callable[P, TCoro]

TGuildChannel = Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.StageChannel,
    discord.ForumChannel,
    discord.CategoryChannel
]