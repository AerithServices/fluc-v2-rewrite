from __future__ import annotations

__all__ = (
    'command_hook',
    'Cooldown',
    'CooldownCheck',
    'CooldownException'
)

import functools
import threading
import discord
import inspect
import aiohttp
import logging
import os
from discord import app_commands
from datetime import timezone, timedelta
from discord.ext import commands
from typing import Optional, Unpack, Callable, Union

from utils.time import now
from utils.enums import Permissions, CooldownType
from utils.state import State
from utils.models import User
from utils.components import RejoinView
from app_types import TCommand, KWCommand, RoleConfig

log = logging.getLogger('fluc')
DEV = os.getenv('DEV', False)

if not DEV:
    with open('config/role.json', 'r') as file:
        role_config = RoleConfig.model_validate_json(file.read())
else:
    role_config = None


class CooldownCheck:
    def __init__(
        self,
        type: CooldownType,
        per: int,
        rate: float,
        id: Optional[str] = None
    ):
        '''
        Initializes :class:`~utils.commands.Cooldown`.

        Parameters
        ----------
        type : :class:`~utils.enums.CooldownType`
            Type of cooldown.
        per : Optional[float]
            Amount of seconds to wait when cooldown has been triggered,
            defaults to 0. Cannot be less than 0.
        rate : Optional[int]
            Number of times command can be used before triggering cooldown,
            defaults to 0. Cannot be less than 0.
        id : Optional[str]
            Custom ID for the check, defaults to None.
        '''
        self.type = type
        'Type of cooldown.'
        self.per = per
        'Amount of seconds to wait when cooldown has been triggered.'
        self.rate = rate
        'Number of times command can be used before triggering cooldown.'
        self.id = id
        'Custom ID for the check.'


class Cooldown:
    def __init__(
        self,
        *checks: CooldownCheck,
        lock: Optional[threading.Lock] = threading.Lock()
    ):
        '''
        Initializes :class:`~utils.commands.Cooldown`.

        Parameters
        ----------
        checks : list[str]
            A list of checks to check.
        lock : Optional[:class:`threading.Lock`]
            Lock used while checking cooldowns, defaults to a new :class:`threading.Lock`.
        '''
        self._cooldowns = {}
        self.lock = lock
        self.update(checks)

    def update(
        self,
        checks: tuple[CooldownCheck, ...]
    ):
        self.checks = checks

    def cleanup(self):
        '''
        Removes dead cooldowns.
        '''
        for key, value in self._cooldowns.copy().items():
            if value['ends'] <= now().timestamp():
                del self._cooldowns[key]

    def check(
        self,
        ctx: Union[commands.Context, discord.Interaction],
        coefficient: float = 1
    ) -> Optional[CooldownException]:
        '''
        Checks if current context should trigger user cooldown.
        Parameters
        ----------
        ctx : `discord.ext.commands.Context`
            Context of interaction.
        coefficient : float
            Coefficient of all cooldowns.

        Returns
        -------
        Optional[:class:`~utils.commands.CooldownException`]
            Raisable cooldown exception object.
        '''
        self.cleanup()
        if isinstance(ctx, commands.Context):
            created_at = ctx.message.created_at
            author = ctx.author
        else:
            created_at = ctx.created_at
            author = ctx.user

        created_at = created_at.replace(tzinfo=timezone.utc)
        timestamp = created_at.timestamp()
        now_timestamp = now().timestamp()
        to_apply = []

        if self.lock:
            self.lock.acquire()
        result: Optional[CooldownException] = None
        try:
            for check in self.checks:
                if check.type is CooldownType.USER:
                    target_id = author.id
                elif check.type is CooldownType.SERVER:
                    if not ctx.guild:
                        return
                    target_id = ctx.guild.id
                elif check.type is CooldownType.CHANNEL:
                    # We're good since commands ran in private channels
                    # are ignored
                    target_id = ctx.channel.id # pyright: ignore[reportOptionalMemberAccess]
                elif check.type is CooldownType.GLOBAL:
                    target_id = 0
                else:
                    raise TypeError('self.type must be CooldownType')

                cd = timedelta(seconds=check.per).total_seconds()
                cd = coefficient * cd
                if check.per and check.rate:
                    cooldown = self._cooldowns.get(target_id)
                    if cooldown:
                        ends: float = cooldown['ends']
                        if ends >= now_timestamp:
                            cooldown['tries'] += 1
                            if cooldown['tries'] >= check.rate:
                                if result:
                                    if result.check.per > check.per:
                                        continue
                                result = CooldownException(
                                    ctx,
                                    check,
                                    self,
                                    round(ends - now_timestamp, 2),
                                    target_id
                                )
                        else:
                            cooldown['ends'] = timestamp + cd
                            cooldown['tries'] = 0
                            cooldown['_sent'] = False
                    else:
                        ends = timestamp + cd
                        default_cooldown = {
                            'ends': ends,
                            'tries': 0
                        }
                        to_apply.append([target_id, default_cooldown])
        finally:
            if not result:
                for target_id, default_cooldown in to_apply:
                    self._cooldowns[target_id] = default_cooldown
            if self.lock:
                self.lock.release()
        return result

    def get_cooldown(self, target_id: int) -> Optional[dict[str, int | float]]:
        return self._cooldowns.get(target_id, None)

    def remove_cooldown(self, target_id: int) -> bool:
        return self._cooldowns.pop(target_id, None) is not None


class CommandFlags:
    def __init__(
        self,
        bypass_protected: bool = False,
        bypass_whitelist: bool = False,
        bypass_blacklist: bool = False,
        bypass_server: bool = False
    ) -> None:
        self.bypass_protected = bypass_protected
        self.bypass_whitelist = bypass_whitelist
        self.bypass_blacklist = bypass_blacklist
        self.bypass_server = bypass_server

    @classmethod
    def none(cls):
        return cls()


def command_hook(
    cooldown: Optional[Cooldown] = None,
    permissions: Permissions = Permissions.USER,
    flags: CommandFlags = CommandFlags.none()
):
    '''
    Hooks discord.py command

    Adds extra checks and parameters to given command.
    '''
    '''
    ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠛⠛⠉⠙⠛⠛⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠛⠉⠀⢀⣠⣤⣶⣶⣶⣶⣦⣤⣀⠈⠛⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠀⢠⣾⣿⡿⠻⠛⠉⣍⣠⣤⡄⠀⠀⠩⠙⠻⢿⣦⡈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⢠⣿⠟⠁⠀⠀⡔⡆⠈⢰⡄⣥⢠⠐⡄⢴⣄⢂⡙⢷⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡏⠀⠀⣾⡟⠀⠀⠀⠀⠘⠁⠂⠈⣳⣼⠀⠀⠋⠘⡏⠈⡶⠈⠇⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠁⠀⢰⡟⠀⠀⠀⠀⠀⠀⡀⠀⠀⠉⡯⣵⠆⡄⠀⠀⠀⡟⢀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠘⠃⠀⠀⠀⠀⠀⣰⠃⡸⠀⠀⣷⡒⠀⠐⢀⠀⠀⠀⠘⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠈⠀⠀⠀⠀⠠⠎⠉⠀⠂⣾⠀⠈⠀⠘⠀⠂⢠⠅⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠀⠀⠀⡀⢀⣄⠐⠄⠀⠀⣍⠂⣠⡾⢀⣔⡁⠀⠀⠄⢀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠸⡀⠐⣾⣿⣷⣶⣿⣟⣥⠾⣋⣤⡹⣿⣿⣶⣶⣾⡇⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠐⢌⢿⣿⣿⣿⣿⣿⣿⣾⣿⣿⡷⢹⣿⣿⣿⣿⠇⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠈⢻⣿⣿⣿⣿⣿⣿⣿⣿⣥⣿⣿⣿⣿⡟⢀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠘⠀⠀⠻⣿⣿⣿⣝⡻⠿⠿⢛⣹⣿⣿⠟⠀⠈⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠳⡌⠻⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⣷⣤⣄⣈⣙⠻⠿⠟⣋⣠⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⢀⡙⠿⣿⣿⣿⣿⣷⣿⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣷⣶⣮⣭⣭⡭⢉⣵⣶⡄⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⣋⣥⣶⣶⣶⣶⣶⣦⣤⣐⠲⠾⠿⣿⣿⣿⣿⣿⣿⣿⡿⢡⣿⣿⣿⣿⣶⣤⡄⠀⣀⣀⣀⣀⣈⣛⡻⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⣼⣿⣿⣿⣿⣿⣿⣿⡿⠟⣛⡩⣍⠓⣒⠲⣶⣲⡯⠭⣙⠰⠿⢟⣫⠽⢭⣭⣶⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣍⡻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠈⠉⠉⠉⠉⠛⠛⠛⢩⡶⢛⣥⡶⠟⣂⠨⣅⡘⢿⣿⣷⣾⣿⣾⡿⠗⣛⣛⣛⣛⡛⠟⠫⠕⠒⢀⣶⣆⠭⣙⠻⠿⠿⠄⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢼⡶⠟⣡⣶⡿⣿⡄⠒⠬⡂⠍⠉⠉⠭⡴⠶⠿⠟⠛⣛⠛⠛⠒⠂⠉⡀⠘⠿⣿⣿⣿⣽⣶⣌⠹⣀⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠶⠿⠟⠛⠉⠩⠤⠬⠤⠤⠤⠤⠤⠤⠤⠤⠤⠤⢤⡄⣈⣉⡀⠀⠀⠉⠒⠤⣄⣉⡙⠻⠿⠛⢠⡙⢷⠸⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣐⣀⣠⣤⣤⣭⣍⣁⣈⣐⣒⡒⠀⠀⠀⠂⠀⠬⠍⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⡌⠂⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠰⢲⣶⣶⣶⣾⣿⣿⣿⣿⣿⣿⣶⣶⣤⣄⡀⠈⠻⣆⠸⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣄⠈⠀⢻⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡆⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⢻⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⣋⣥⣶⣶⡌⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡄⢻⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⣸⣿⣿⣿⣿⠏⣴⠿⡛⢉⠻⣿⡌⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⣭⣭⣂⠻⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⢀⣿⣿⣿⣿⡏⣼⡏⣜⣁⣾⠀⣿⣷⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢸⣿⣿⠋⡅⡜⢿⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⢸⣿⣿⣿⣿⡇⣿⣷⣜⣃⣠⣾⣿⠇⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢸⣿⣿⡤⣥⣙⢸⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⢸⣿⣿⣿⣿⣷⡘⠿⣿⣿⣿⡿⢋⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⢻⣿⣿⣤⣤⢸⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠈⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣍⠻⠿⠟⢸⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⡀⢀⠀⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⣼⣿
⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠘⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠁⣠⣾⠇⣾⣷⣄⠈⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢰⣿⣿
⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠙⠙⡿⣻⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠿⠛⢉⣀⣴⣾⣿⣿⢰⣿⣿⣿⣷⣄⡈⠛⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⡀⣼⣿⣿
⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠛⠛⠛⠛⠛⠉⣁⣠⣴⣾⣿⣿⣿⣿⣿⣟⣸⣿⣿⣿⣿⣿⣿⣶⣄⣀⠙⠻⠿⠿⣿⣿⣿⣿⡿⠿⠛⢉⣴⣿⠁⣿⣿⡟
⣿⣿⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡆⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⡶⠀⠀⣴⣖⢶⡖⢂⣴⣿⣿⠏⣼⣿⣿⠃
⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⢀⡼⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠁⠀⢈⢣⠘⢿⣿⠏⣼⣿⣿⡟⠀
⠹⠯⠭⠭⠭⠭⠉⠭⠁⠀⠀⠀⠀⠀⠀⡠⠊⠀⠀⣤⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⢀⣀⠁⢊⣡⣬⣭⣭⣭⠅⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡏⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⢛⠃⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⣀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⡻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣫⣾⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢀⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣭⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⣩⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣄⡙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢃⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⢰⡖⠀⠀
⠀⠀⠀⠀⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⢁⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡆⠂⠀⠀
⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠈⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢁⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀
⠀⠀⠀⠀⠀⢹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡆⣏⢽⣿⣿⣿⣿⣿⡍⣿⣿⣿⣿⣿⡏⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠙⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⢸⡞⣿⣿⣿⣿⠀⣸⣿⣿⡟⠙⣵⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠁⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠻⠛⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡧⠹⣿⣿⣿⠀⢻⣿⣿⢡⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠋⠉⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠛⠛⠛⠛⢓⣪⣭⣽⠿⢻⢝⡯⠇⡇⣘⠘⠉⠛⡿⢐⢿⠿⠻⠊⠉⠉⠙⠉⠉⠉⠀⠉⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀

 ^^ VEX'S SISTER
    '''
    def decorator(coro: TCommand):
        async def predicate(ctx: Union[commands.Context, discord.Interaction]) -> bool:
            nonlocal user

            if DEV:
                return True
            if isinstance(ctx, commands.Context):
                author = ctx.author
            else:
                author = ctx.user

            # Global check for all commands
            # Make sure command is ran in a server
            if not flags.bypass_server:
                assert ctx.guild
            
            if ctx.guild:
                if not flags.bypass_protected:
                    # If it ever gets added to protected server ...
                    assert ctx.guild.id not in State.protected_servers

            user = await State.db.get_user(author.id)
            if permissions is Permissions.PUBLIC:
                # Since PUBLIC only bypasses requirement of
                # the user existing we can make a temporary user
                if not user:
                    user = User.new(State, author.id)
            # Drop if user was not found
            assert user
            if not flags.bypass_whitelist and not user.is_elevated:
                if ctx.guild:
                    if State.whitelisted_servers:
                        assert ctx.guild.id in State.whitelisted_servers
                    # else: Temporary bypass restrictions. 
                    # It takes ~30secs to cache all servers after connecting.
                    # While we don't have access to those servers, we cannot append them to whitelisted_servers.
                    # Because of this users won't be able to run commands while it's caching servers.
            if not flags.bypass_blacklist:
                assert not user.is_blacklisted
            if permissions is Permissions.OWNER_ONLY:
                assert user.is_owner
            if permissions is Permissions.ELEVATED:
                assert user.is_elevated
            if user.is_elevated:
                return True
            if permissions is Permissions.MOD:
                # This code is cursed
                assert role_config
                assert ctx.guild
                assert ctx.guild.id == State.verify_config.main_server 
                assert author in ctx.guild.members
                role = ctx.guild.get_role(role_config.moderator)
                member = ctx.guild.get_member(author.id)
                assert member
                assert role in member.roles
            if permissions is Permissions.PREMIUM:
                if not user.is_premium:
                    if isinstance(ctx, discord.Interaction):
                        await ctx.response.send_message('This is a premium command. Check #premium in main server.', ephemeral=True)
                    return False
            async with aiohttp.ClientSession('https://discord.com') as session:
                session.headers.update({
                    'authorization': f'Bot {os.getenv('UTILITY_TOKEN')}',
                    'content-type': 'application/json'
                })
                main_server = State.verify_config.main_server
                async with session.get(f'/api/guilds/{main_server}/members/{author.id}') as response:
                    # The HTTPS request failed most likely with 404 Not Found
                    if not response.ok:
                        rejoin_cd = getattr(State, 'rejoin_cd', None)
                        if not rejoin_cd:
                            rejoin_cd = Cooldown(CooldownCheck(CooldownType.USER, 60, 1))
                            State.rejoin_cd = rejoin_cd
                        exc = rejoin_cd.check(ctx)
                        if exc:
                            raise exc
                        view = RejoinView(author.id)
                        if isinstance(ctx, discord.Interaction):
                            await ctx.response.send_message(embed=view.embed, view=view, ephemeral=True)
                        else:
                            await ctx.send(embed=view.embed, view=view)
                        return False
            if cooldown:
                cooldown_coefficient = 1
                if user.is_premium:
                    cooldown_coefficient = State.cooldown_coefficient
                exc = cooldown.check(ctx, cooldown_coefficient)
                if exc:
                    if isinstance(ctx, discord.Interaction):
                        # Interactions have big delay (server-side thing) so we don't need
                        # to manually check when last interaction was sent
                        if exc.check.type is CooldownType.USER:
                            who = 'You are'
                        elif exc.check.type is CooldownType.SERVER:
                            who = 'This server is'
                        elif exc.check.type is CooldownType.CHANNEL:
                            who = 'This channel is'
                        else:
                            who = 'This command is globally'
                        msg = f'{who} on cooldown. Try again in {exc.retry_in}s'
                        await ctx.response.send_message(f'{who} on cooldown. Try again in {exc.retry_in}s', ephemeral=True)
                        assert None
                    raise exc
            return True
        
        async def check(*args, **kwargs) -> bool:
            try:
                return await predicate(*args, **kwargs)
            except AssertionError as exc:
                # Supress all errors because 
                # cooldown has not been applied yet
                return False

        @commands.check(check)
        @app_commands.check(check)
        async def callback(*args, **kwargs):
            # Context can only be 1st or 2nd arg.
            # 2nd when the command is a part of a Cog.
            for i in range(2):
                if isinstance(args[i], (commands.Context, discord.Interaction)):
                    ctx: Union[commands.Context, discord.Interaction] = args[i]
                    break
            else:
                # Should be unreachable
                raise Exception('Unreachable code.')
            
            if isinstance(ctx, commands.Context):
                author = ctx.author
            else:
                author = ctx.user

            if isinstance(ctx, commands.Context):
                args = ctx.args
                kwargs = ctx.kwargs
                for arg in args.copy():
                    if ctx.command and ctx.command.name == 'help':
                        # Skip help command
                        break
                    if isinstance(arg, (str, float, int, bool)):
                        # Arg is not context, instance of Command
                        if user and user.is_premium:
                            continue
                        # Remove arg for non premium users
                        args.remove(arg)
            else:
                # for discord.Interaction
                # args and kwargs are passed directly in callback.
                # Nothing to do here
                pass
            if pass_user:
                kwargs['user'] = user
            log.info(f'Command {callback.__name__} ran by {author}#{author.id}')
            await coro(*args, **kwargs)

        # Add command to state
        user: Optional[User]
        cmd = Command(callback=coro, cooldown=cooldown, permissions=permissions)
        pass_user = False
        State.add_command(cmd)

        # Copy all coro attributes to callback to
        # avoid registration issues. This removes the
        # need of setting command name for each command
        # and adding other unnecessary stuff.
        functools.update_wrapper(callback, coro)

        signature = inspect.signature(callback)
        for _, param in signature.parameters.items():
            if param.kind == param.VAR_KEYWORD:
                pass_user = True
                break
        return callback
    return decorator


class CooldownException(commands.CommandError):
    def __init__(
        self,
        ctx: Union[commands.Context, discord.Interaction],
        check: CooldownCheck,
        cooldown: Cooldown,
        retry_in: float,
        target_id: int
    ):
        self.ctx = ctx
        self.check = check
        self.cooldown = cooldown
        self.retry_in = retry_in
        self.target_id = target_id


class Command:
    callback: Optional[Callable]
    'The actual command.'
    cooldown: Optional[Cooldown]
    'The :class:`~utils.commands.Cooldown` for this command.'
    description: Optional[str]
    'Description of command.'
    name: str
    'Name of command.'
    permissions: Permissions
    'Permissions for command.'
    def __init__(
        self,
        **kwargs: Unpack[KWCommand]
    ):
        self.update(**kwargs)

    def update(self, **kwargs: Unpack[KWCommand]):
        self.callback = kwargs.get('callback')
        self.cooldown = kwargs.get('cooldown')
        self.description = kwargs.get('description')
        self.permissions = kwargs.get('permissions', Permissions.USER)
        if not self.description and self.callback:
            self.description = self.callback.__doc__
        name = kwargs.get('name')
        if not name and self.callback:
            self.name = self.callback.__name__
        elif name:
            self.name = name
        else:
            raise ValueError('"name" is a required argument at this time.')