from __future__ import annotations

__all__ = (
    'KWCommand',
    'KWNow'
)

from .aliases import TCommand
from discord.ext import commands
from typing import TypedDict, NotRequired, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from utils.enums import Permissions
    from utils.commands import Cooldown

class KWNow(TypedDict, total=False):
    days: int
    seconds: int
    microseconds: int
    milliseconds: int
    minutes: int
    hours: int
    weeks: int

class KWCommand(TypedDict, total=False):
    callback: Optional[TCommand]
    'Callback for command.'
    cooldown: Optional[Cooldown]
    ':class:`~utils.commands.Cooldown` for command.'
    description: str
    'Description of the command. Not required if ``callback`` was passed.'
    name: str
    'Name of command. Not required if ``callback`` was passed.'
    permissions: Permissions
    'Permissions of command.'