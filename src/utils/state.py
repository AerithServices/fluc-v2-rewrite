from __future__ import annotations

__all__ = (
    'State',
)

import asyncio
import utils
from datetime import datetime
from utils.xorshift32 import Xorshift32
from utils.database import Database
from app_types import DatabaseConfig, VerifyConfig
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from utils.font import FontGen, PhraseGen
    from utils.commands import Command, Cooldown

class State:
    protected_servers: list[int] = []
    whitelisted_servers: list[int] = []
    owner_ids: list[int] = []
    command_prefixes: list[str] = []
    proxies: list[str] = []
    cooldown_coefficient: float = 1
    nconntries = 0
    is_ready: bool = False
    db: Database
    verify_config: VerifyConfig
    _commands: dict[str, Command] = {}
    oauth_states: dict[str, datetime] = {}
    fontgen: FontGen
    phrasegen: PhraseGen
    xs32 = Xorshift32()
    avatars = []
    rejoin_cd: Optional[Cooldown]
    main_task: asyncio.Task
    protected_tasks: list[str] = []
    shutdown = asyncio.Event()
    tlds = []

    @classmethod
    def add_command(cls, command: Command):
        '''
        Adds command to State

        Parameters
        ----------
        command : :class:`~utils.commands.Command`
            The command to add.
        '''
        cls._commands[command.name] = command

    @classmethod
    def remove_command(cls, command: Command):
        '''
        Removes command from State.

        Parameters
        ----------
        command : Command
            The command to remove.

        Raises
        ------
        KeyError
            The command was not found.
        '''
        cls._commands.pop(command.name)

    @classmethod
    def get_command(cls, name: str) -> Command:
        '''
        Returns command and it's cooldown.

        Parameters
        ----------
        name : str
            Name of command to search.

        Raises
        ------
        KeyError:
            The command was not found.

        Returns
        -------
        tuple[TCommand, :class:`~utils.commands.Cooldown`]
            Tuple containing the command and :class:`~utils.commands.Cooldown` object.
        '''
        return cls._commands[name]
    
    @classmethod
    def is_elevated(cls, user_id: int) -> bool:
        if user_id in cls.owner_ids:
            return True
        return False
    
    @classmethod
    def load_fonts(cls, *names) -> None:
        fonts = ''
        for file_name in names:
            with open(f'data/{file_name}', encoding='utf-8') as file:
                font = file.read() + '\n'
                fonts += font
        fonts = fonts.strip()
        fontgen = utils.FontGen(fonts)
        cls.fontgen = fontgen
    
    @classmethod
    def load_phrases(cls, name: str, *names) -> None:
        fonts = ''
        for file_name in names:
            with open(f'data/{file_name}', encoding='utf-8') as file:
                font = file.read() + '\n'
                fonts += font
        fonts = fonts.strip()
        phrasegen = utils.PhraseGen(fonts, name)
        cls.phrasegen = phrasegen

    @classmethod
    def load_tlds(cls, file_name: str) -> None:
        lines = []
        with open(f'data/{file_name}', encoding='utf-8') as file:
            for line in file.readlines():
                lines.append(line.strip())
        cls.tlds = lines

    @classmethod
    def get_phrases(cls) -> list[str]:
        phrases = utils.fmt_phrases(cls.phrasegen, cls.fontgen)
        return phrases

    @classmethod
    def get_phrase(cls) -> str:
        phrases = cls.get_phrases()
        return cls.xs32.choice(phrases)

    @classmethod
    async def connect_db(cls, db_config: DatabaseConfig):
        await cls.db.connect(db_config)

    @classmethod
    def protect_task(cls, task: str):
        cls.protected_tasks.append(task)

    @classmethod
    def unprotect_task(cls, task: str):
        cls.protected_tasks.remove(task)

    @classmethod
    def can_shutdown(cls) -> bool:
        return not cls.protected_tasks

State.db = Database(State)
