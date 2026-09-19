import asyncio
import discord
import logging
import traceback
import aiohttp
import os
import uuid
import copy
import utils
from collections import defaultdict
from utils.commands import CooldownException, Cooldown, CooldownType
from utils.state import State
from utils.models import User, Backup
from utils.modified import ConnectedBot, EventCog
from discord.ext import commands
from discord.ext.tasks import loop as task_loop
from typing import Optional

log = logging.getLogger('fluc')
DEV = os.getenv('DEV', False)
locks = defaultdict(asyncio.Lock)

class Events(EventCog):
    def __init__(self, bot: ConnectedBot):
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None
        super().__init__()

    @task_loop(seconds=10)
    async def server_cleanup(self):
        # if len(self.bot.guilds) > 70:
        def key(guild: discord.Guild) -> int:
            me = guild.me
            if me and me.joined_at:
                return int(me.joined_at.timestamp())
            return 0

        oldest = sorted(self.bot.guilds, key=key)
        # Exclude protected servers
        for guild in self.bot.guilds:
            if guild.id in State.protected_servers:
                oldest.remove(guild)

        # Excess is the amount of servers we need to leave.
        # This will be a negative integer so we use that to
        # get the last x servers. 
        excess = len(self.bot.guilds) - 70
        for guild in oldest[:excess]:
            await guild.leave()
            await asyncio.sleep(1)

    @task_loop(seconds=30)
    async def api_status(self):
        await utils.api_status(self.bot)

    @commands.Cog.listener()
    async def on_ready(self):
        # Set up command aliases
        def make_aliases(parts: list[str]) -> list[str]:
            extra = []
            if 'delete' in parts:
                parts2 = parts.copy()
                index = parts.index('delete')
                parts2.remove('delete')
                parts2.insert(index, 'del')
                extra.extend(make_aliases(parts2))
            return [
                # command_test => ct
                ''.join([part[0] for part in parts]),
                # command_test => commandtest
                ''.join([part for part in parts]),
                # command_test => ctest
                ''.join([part[0] if part == parts[0] else part for part in parts])
            ] + extra
        
        if State.is_ready:
            # The bot reconnected after session got invalidated.
            # Close the bot and force full reconnect
            await self.bot.close()
            return

        # Mark bot as connected so it doesn't timeout
        State.is_ready = True
        for command in self.bot.commands:
            extra_names = list(command.aliases)
            aliases = []
            for extra_name in extra_names:
                parts = extra_name.split('_')
                if len(parts) > 1:
                    aliases.extend(make_aliases(parts))
                else:
                    aliases.append(extra_name)
            name = command.name
            aliases.extend(make_aliases(name.split('_')))
            aliases.append(name)
            # Remove dublicates
            aliases = tuple(set(aliases))
            command.aliases = aliases
            # Manually register command aliases since aliases get added
            # to commands only once after creation
            for alias in aliases:
                self.bot.all_commands[alias] = command

        # Automatically leave old servers
        self.server_cleanup.start()
        # Checks if bot gets banned,
        # and if so, reconnect
        self.api_status.start()
        for server in self.bot.guilds:
            State.whitelisted_servers.append(server.id)
        log.info(f'Connected as {self.bot.user} (ID: {self.bot.user.id})')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exc: Exception, *args):
        if isinstance(exc, commands.CheckFailure):
            return
        async with locks['on_command_error']:
            if not ctx.command:
                return
            command = State.get_command(ctx.command.name)
            cooldown: Cooldown = command.cooldown # type: ignore 
            if isinstance(exc, CooldownException):
                cooldown_ = cooldown.get_cooldown(exc.target_id)
                if cooldown_ and not cooldown_.get('_sent'):
                    cooldown_['_sent'] = True
                    if exc.check.type is CooldownType.USER:
                        who = 'You are'
                    elif exc.check.type is CooldownType.SERVER:
                        who = 'This server is'
                    elif exc.check.type is CooldownType.CHANNEL:
                        who = 'This channel is'
                    else:
                        who = 'This command is globally'
                    msg = f'{who} on cooldown. Try again in {exc.retry_in}s'
                    await ctx.reply(msg)
                return
            else:
                exception = ''.join(traceback.format_exception(exc))
                log.error(f'Unhandled exception:\n{exception}')
            await ctx.reply(str(exc))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        async def leave():
            try:
                await guild.leave()
            except discord.NotFound:
                # Most likely kicked by anti-raid bot
                return

        if DEV:
            return
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.user:
                    if entry.target == self.bot.user:
                        inviter = entry.user
                        break
            else:
                # Could not find bot inviter
                log.error(f'Could not get guild inviter for {guild.id}.')
                await leave()
                return
        except (discord.Forbidden, discord.NotFound):
            # Slow ahh anti r4id bots
            await leave()
            return
        
        user = await State.db.get_user(inviter.id)
        if user and user.is_blacklisted:
            await leave()
            return

        State.whitelisted_servers.append(guild.id)
        asyncio.create_task(self.create_backup(copy.copy(guild)))
        if not user:
            # Temporary user for default settings
            user = User.new(State, 0)

        async def fetch(uri: Optional[str]) -> Optional[bytes]:
            try:
                if uri:
                    async with self.session.get(uri) as response:
                        response.raise_for_status()
                        return await response.read()
            except:
                pass
        avatar = None
        banner = None
        banner_url = user.settings.bot_banner
        avatar_url = user.settings.bot_avatar
        if avatar_url:
            avatar = await fetch(avatar_url)
        if banner_url:
            banner = await fetch(banner_url)
        try:
            await guild.me.edit(
                nick=user.settings.bot_nick,
                bio=user.settings.bot_bio,
                avatar=avatar,
                banner=banner
            )
        except discord.HTTPException:
            # Most likely rate limited
            pass

    @commands.Cog.listener()
    async def on_disconnect(self):
        # Reconnect manually
        await utils.abort(self.bot, None)

    async def create_backup(self, guild: discord.Guild):
        data = await utils.create_backup(guild)
        key = str(uuid.uuid4())
        backup = Backup(
            key,
            utils.now().date(),
            guild.id,
            data
        )
        await State.db.set_backup(backup)

    async def cog_unload(self):
        if self.api_status.is_running():
            self.api_status.cancel()
        if self.server_cleanup.is_running():
            self.server_cleanup.cancel()

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = self.bot.http._HTTPClient__session # pyright: ignore[reportAttributeAccessIssue]
        return self._session # pyright: ignore[reportReturnType]
