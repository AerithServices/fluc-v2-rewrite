__all__ = (
    'runner',
    'get_tokens',
    'strip_ip',
    'is_none',
    'verify_user',
    'Emoji',
    'ascii',
    'strip_special',
    'api_status',
    'get_session',
    'get_iter',
    'safe_chr',
    'numgen',
    'abort'
)

import os
import re
import utils
import logging
import aiomysql
import asyncio
import discord
import string
import aiohttp
import traceback
from utils.state import State
from utils.modified import ConnectedBot
from app_types import DatabaseConfig, TCoro, RoleConfig, EmojiConfig
from typing import Callable, Iterable, Optional, Generator

log = logging.getLogger('fluc')

class Emoji:
    def __init__(self, emoji_config: EmojiConfig) -> None:
        self.emoji_config = emoji_config

    def _construct(self, name: str, emoji_id: int) -> str:
        return f'<:{name}:{emoji_id}>'

    @property
    def upvote(self) -> str:
        return self._construct('upvote', self.emoji_config.upvote)

    @property
    def downvote(self) -> str:
        return self._construct('downvote', self.emoji_config.downvote)

    @property
    def checkmark(self) -> str:
        return self._construct('checkmark', self.emoji_config.checkmark)

    @property
    def crossmark(self) -> str:
        return self._construct('crossmark', self.emoji_config.crossmark)

async def abort(bot: ConnectedBot, exc: Optional[str] = None):
    try:
        await asyncio.wait_for(wait_shutdown(), timeout=15)
    except (asyncio.TimeoutError, KeyboardInterrupt):
        pass
    log.error(f'Reconnecting: {exc}')
    bot.clear()
    log.debug('Bot cleared.')
    # At this point the bot decides to reconnect...?
    # Live logs:
    # 2026-08-28 18:37:39 [ DBG ] fluc: Bot cleared.
    # 2026-08-28 18:37:39 [ DBG ] discord.gateway: Received WSMessage(type=<WSMsgType.CLOSED: 257>, data=None, extra=None)
    # 2026-08-28 18:37:39 [ DBG ] discord.gateway: Websocket closed with 1006, attempting a reconnect.
    # 2026-08-28 18:37:39 [ DBG ] discord.client: Got a request to RESUME the websocket.
    # Even tho we requested a full close.
    # But it can't reconnect because the session is closed, the bot hangs before shutdown is set.
    # So instead of investigating this further, I am just gonna set reconnect=False when connecting.
    # This shit hangs so we have to close it manually
    # await bot.close()
    bot._ready.clear()
    log.debug('Ready event cleared.')
    State.shutdown.set()
    log.debug('State.shutdown set.')
    try:
        await bot.session.close()
        log.debug('Bot session closed.')
    except Exception:
        log.debug(f'Exception occured when closing bot session: {traceback.format_exc()}')
    try:
        await bot.http.close()
        log.debug('Closed HTTPClient')
    except Exception:
        log.debug(f'Exception occured when closing HTTPClient: {traceback.format_exc()}')
    try:
        log.debug('Closing bot...')
        await asyncio.wait_for(bot.close(), 15)
        log.debug('Bot closed.')
    except asyncio.TimeoutError:
        log.debug('Timeout (15s)')
    except Exception:
        log.debug(f'Exception while closing bot: {traceback.format_exc()}')
    return False

async def api_status(bot: ConnectedBot, ignore_webhook: bool = False) -> bool:
    # So this gets called again after it requests a reconnect
    # and since the bot is closed it will hang here for some reason.
    # Yet I am not 100% sure this hangs the bot on reconnect
    if bot.session.closed or bot.is_closed() or not bot.user:
        log.debug('api_status was ran on closed bot.')
        return False
    try:
        await bot.http.get_user(bot.user.id)
        if ignore_webhook:
            return True
        webhook_id = os.getenv('TEST_WEBHOOK_ID')
        webhook_token = os.getenv('TEST_WEBHOOK_TOKEN')
        url = f'https://discord.com/api/webhooks/{webhook_id}/{webhook_token}'
        response = await bot.session.post(url, json={'content': 'ping'})
        raise discord.HTTPException(response, '')
    except (discord.HTTPException, RuntimeError) as exc:                
        if isinstance(exc, RuntimeError):
            # Usually connection closed (temporary, irrelevant)
            return True
        response = exc.response
        if isinstance(response, aiohttp.ClientResponse):
            status = response.status
        else:
            status = response.status_code
        # According to discord.py this header is excluded
        # when the client gets blocked
        if not response.headers.get('via') or status == 429:
            log.debug('Rate limited. Waiting for timeout (15 sec)')
            # ggs
            await abort(bot, str(exc))
            return False
        return True

async def wait_shutdown():
    while not State.can_shutdown():
        await asyncio.sleep(0.1)

async def runner(mainloop: Callable[..., TCoro]):
    try:
        with open('config/proxies.txt') as file:
            proxies = [line.strip() for line in file.readlines()]
    except FileExistsError:
        proxies = []

    with open('config/database.json') as file:
        db_config = DatabaseConfig.model_validate_json(file.read())

    valid_proxies = await utils.test_proxies(proxies)
    for proxy in proxies:
        if proxy not in valid_proxies:
            log.warning(f'Found invalid proxy: {proxy}')
    State.proxies = valid_proxies

    log.info('Connecting to Database...')
    try:
        await State.connect_db(db_config)
    except aiomysql.OperationalError as exc:
        text = utils.strip_ip(str(exc))
        log.error(text)
        return

    num_reconnects = 0
    # Automatically close database on errors
    async with State.db:
        while True:
            # Could be set from previous connection
            State.shutdown.clear()
            State.is_ready = False
            State.nconntries += 1
            log.debug('New mainloop created.')
            task = asyncio.create_task(mainloop(), name='mainloop')
            State.main_task = task
            for _ in range(60):
                if State.is_ready or task.done():
                    break
                await asyncio.sleep(1)
            if task.done():
                # Raises if task raised an exception
                if task.cancelled():
                    reconnect = True
                else:
                    reconnect = task.result()
                if not reconnect:
                    break
                else:
                    if num_reconnects > 4:
                        await asyncio.sleep(num_reconnects / 2)
                    #    log.info('Failed to reconnect after 3 attempts. Closing.')
                    #    break
                    log.info('Reconnecting...')
                    num_reconnects += 1
                    continue
            if not State.is_ready:
                # Timeout
                log.warning('Discord READY was not received 60 seconds after connecting. Retrying...')
                task.cancel(msg='Timeout')
            # Wait until task returns
            # Wait at most 6 hours until automatic reconnect
            timeout = False
            num_reconnects = 0
            try:
                log.debug('Shielding and waiting for timeout...')
                await asyncio.wait_for(
                    # Do not cancel task on timeout
                    asyncio.shield(State.shutdown.wait()),
                    timeout=60 * 60 * 6
                )
            except asyncio.TimeoutError as exc:
                log.info(f'Reconnecting due to timeout')
                timeout = True
                try:
                    log.debug('Waiting for shutdown (60 sec til timeout)..')
                    await asyncio.wait_for(
                        wait_shutdown(),
                        timeout=60
                    )
                except Exception:
                    pass
                task.cancel(msg='Timeout')
                log.debug('Task killed.')
            except Exception as exc:
                log.error(traceback.format_exc())
            else:
                if not task.done():
                    task.cancel(msg='Shutdown')
                    log.debug('Task killed.')
            if not task.done():
                # I know this is bad practise, but something's not
                # closing and I need to figure out what it is
                # (causes up to 1hr downtime)
                # TOOD: fix
                log.debug('Waiting for bot to return...')
                result = await asyncio.gather(task, return_exceptions=True)
                if result and result[0] is False and not timeout:
                    # Break if returned False
                    break
            log.info('Reconnecting...')

def get_tokens() -> list[str]:
    tokens = [
        os.getenv('NUKE_TOKEN', ''),
        os.getenv('UTILITY_TOKEN'),
        os.getenv('RAID_TOKEN'),
        os.getenv('MIAN_TOKEN')
    ]
    for token in tokens.copy():
        if not token:
            # Remove invalid tokens
            tokens.remove(token)
    return tokens

def strip_ip(text: str, replace: str = 'x', keep_last: bool = True):
    ip_re = r'(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])'
    match = re.search(ip_re, text)
    if match:
        ip = match.group()
        replace_full = replace + f'.{replace}' * 3
        if keep_last:
            # Replace IP with "x.x.x.original"
            parts = ip.split('.')
            last = parts[-1]
            replaced = replace_full.replace(replace, last, count=1) 
            # Reverse "replaced"
            return text.replace(ip, replaced[::-1])
        # Replace ip with "x.x.x.x"
        return text.replace(ip, replace_full)
    # IP not found in text
    return text

def is_none(string: str) -> bool:
    return string.lower in ('null', '0', 'none', '-', 'nul', 'nil')

def ascii(string: str) -> str:
    encoded = string.encode()
    decoded_ascii = encoded.decode('ascii', errors='ignore')
    return decoded_ascii

def strip_special(string_: str) -> str:
    new = ascii(string_)
    allowed = string.digits + string.ascii_letters
    new_chars = [char for char in new if char in allowed]
    return ''.join(new_chars)

async def verify_user(member: discord.Member, role_config: RoleConfig, *, force_member: bool = False) -> bool:
    '''
    "Verifies" a user in the main server.

    If any special role found, removes it if user is not eligible for the role.

    Parameters
    ----------
    member : :class:`discord.Member`
        Member to verify.
    role_config : :class:`~utils.RoleConfig`
        Special role config.

    Returns
    -------
    bool
        Whether the user was updated.
    '''
    db_roles = [
        role_config.super,
        role_config.premium,
        role_config.blacklisted,
        role_config.user,
        role_config.rep,
        role_config.limited
    ]
    user = await State.db.get_user(member.id)
    if not user:
        was_updated = False
        if force_member:
            for role in member.roles:
                if role.id == db_roles[3]:
                    break
            else:
                role = discord.Object(id=db_roles[3])
                await member.add_roles(role)
                was_updated = True
        for role in member.roles:
            if role.id in db_roles:
                if role.id == db_roles[3]:
                    # Do not remove user role
                    continue
                await member.remove_roles(role)
                was_updated = True
        return was_updated
    if user.is_blacklisted:
        server_role = member.guild.get_role(db_roles[2])
        assert server_role
        to_keep = []
        for role in member.roles:
            if not role.is_assignable():
                to_keep.append(role)
        roles = [server_role] + to_keep
        if roles != member.roles:
            await member.edit(roles=set(roles), reason='Member verify')
            return True
        return False
    if user.flags.limited:
        server_role = member.guild.get_role(db_roles[5])
        assert server_role
        to_keep = []
        for role in member.roles:
            if not role.is_assignable():
                to_keep.append(role)
        roles = [server_role] + to_keep
        if roles != member.roles:
            await member.edit(roles=set(roles), reason='Member verify')
            return True
        return False
    roles = [db_roles[3]]
    if user.premium.is_premium:
        # We are not checking whether the user has premium perks,
        # but rather whether the user is premium
        roles.append(db_roles[1])
    if user.is_elevated:
        roles.append(db_roles[0])
    if user.flags.limited:
        roles.append(db_roles[5])
    discord_roles: list[discord.Role] = []
    for role in roles:
        server_role = member.guild.get_role(role)
        if server_role:
            discord_roles.append(server_role)

    # Combine member roles with new roles and remove dublicates
    new_roles: list[discord.Role] = []
    # new_roles = list(set(member.roles + discord_roles))
    wanted_roles = {role_id for role_id in roles}
    new_role_ids = set()
    for role in member.roles + discord_roles:
        if role.id in new_role_ids:
            # Remove dublicates
            continue
        # Only check special roles
        if role.id in db_roles:
            if role.id not in wanted_roles:
                if role.is_assignable():
                    # Role was assigned but the user does not have it
                    # so remove it
                    continue
        new_roles.append(role)
        new_role_ids.add(role.id)
    rep = member.guild.get_role(role_config.rep or 0)
    if rep:
        meet_requirements = False
        if member.primary_guild.id == member.guild.id:
            meet_requirements = True
        if not meet_requirements:
            for activity in member.activities:
                if isinstance(activity, discord.CustomActivity):
                    if activity.state and '/fluc' in activity.state:
                        meet_requirements = True
                        break
        if meet_requirements:
            new_roles.append(rep)
    # We removed all nonetypes from discord_roles earlier.
    # When comparing set order is ignored
    if set(member.roles) == set(new_roles):
        return False
    new_roles_ids = [role.id for role in new_roles]
    member_roles_ids = [role.id for role in member.roles]
    limited = db_roles[5]
    await member.edit(roles=new_roles, reason='Member verify')
    if limited in new_roles_ids and limited not in member_roles_ids:
        # User just got limited
        # Fk me for hardcoding this but I cba editing config
        channel = member.guild.get_channel(1534629197115556017)
        if isinstance(channel, discord.TextChannel):
            await channel.send(f'{member.mention} you have been limited.', delete_after=60)
    return True

def get_session(self: ConnectedBot):
    if not getattr(self, '_session', None):
        self._session = self.http._HTTPClient__session # pyright: ignore[reportAttributeAccessIssue]
    return self._session # pyright: ignore[reportReturnType]

def get_iter[T](iter: Iterable, value: T) -> Optional[T]:
    '''
    Returns item from ``iter`` if ``value`` == item.

    Parameters
    ----------
    iter: Iterable
        Object that could contain value.
    value: Any
        Value to search for.

    Returns
    -------
    Optional[T]
        Item from ``iter`` if ``value`` matches it.
    '''
    return next((item for item in iter if item == value), None)

def safe_chr(n: int) -> str:
    '''Converts number to a printable character.'''
    n %= 0x110000
    if 0xD800 <= n <= 0xDFFF:
        n = 0xE000
    return chr(n)

def numgen() -> Generator[int, None, None]:
    '''Generates continuous, incrementing numbers.'''
    i = 0
    while True:
        i += 1
        yield i