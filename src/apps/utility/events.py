import logging
import discord
import utils
import string
import asyncio
import traceback
import utils
import uuid
from collections import defaultdict
from datetime import timedelta
from discord.ext import commands
from discord.ext.tasks import loop
from utils.modified import ConnectedBot, EventCog
from utils.state import State
from utils.models import User
from app_types import RoleConfig, EmojiConfig, BotConfig

log = logging.getLogger('fluc')
xs32 = utils.Xorshift32()

class Events(EventCog):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot
        with open('config/bot.json') as file:
            self.bot_config = BotConfig.model_validate_json(file.read())
        with open('config/role.json') as file:
            self.role_config = RoleConfig.model_validate_json(file.read())
        with open('config/emoji.json') as file:
            emoji_config = EmojiConfig.model_validate_json(file.read())
        self.emoji = utils.Emoji(emoji_config)
        self.locks = defaultdict(asyncio.Lock)
        self.local = {}

    async def fix_name(self, member: discord.Member):
        '''
        Updates member name.

        Strips utf-8 characters.
        Sets to member's username if the new nick is shorter than 2 characters.

        Parameters
        ----------
        member : :class:`discord.Member`
            Member to update.
        '''
        names = [member.nick, member.display_name, member.name]
        for name in names.copy():
            if not name:
                names.remove(name)
        blacklist = [tld for tld in State.tlds] + ['bio', 'store']
        new_nick = None
        for name in names:
            name = utils.ascii(name)
            if name.startswith('!'):
                name = name.lstrip('!')
                name = name.strip()
            
            if any(word in name.lower() for word in blacklist):
                continue
            if '/' in name:
                try:
                    # / is prefix for Discord invites
                    index = name.index('/')
                    next_char = name[index + 1]
                    if next_char in string.ascii_letters + string.digits:
                        continue
                except (ValueError, IndexError):
                    pass
            if len(name) < 2:
                continue
            if len(set(name)) <= 1:
                # Repeated character
                continue
            new_nick = name
            break
        if not new_nick:
            npc_names = [
                'jack',
                'star',
                'coder',
                'dude',
                'bro',
                'zack',
                'omar'
            ]
            new_nick = xs32.choice(npc_names)
        for activity in member.activities:
            if isinstance(activity, (discord.CustomActivity)):
                state = activity.state
                if not state:
                    continue
                # Skip checks for /fluc (our vanity)
                state = state.replace('/fluc', '')
                if '/' in state:
                    # / is prefix for Discord invites
                    index = state.index('/')
                    next_char = state[index + 1]
                    # Make sure it's not /: (emoji) or smth
                    if next_char in string.ascii_letters + string.digits:
                        if not new_nick.startswith('z'):
                            # Add z to their name so they appear last in member list
                            new_nick = 'z' + new_nick[:31]
        if new_nick != member.display_name:
            await member.edit(nick=new_nick)

    @loop(hours=6)
    async def member_maintenance(self):
        guild = self.bot.get_guild(State.verify_config.main_server)
        if not guild:
            log.critical('Bot not in main server. Please add the bot back immediately.')
            raise
        # Includes verified members
        role = discord.Object(id=self.role_config.user)
        try:
            await asyncio.wait_for(guild.prune_members(days=7 * 3, roles=[role]), 5)
        except asyncio.TimeoutError:
            pass
        main_server_id = State.verify_config.main_server
        main_server = self.bot.get_guild(main_server_id)
        if not main_server:
            # Should be unreachable
            log.error('Failed to get main_server.')
            return
        boosters = main_server.premium_subscribers
        now = utils.now().date()
        for booster in boosters:
            user = await State.db.get_user(booster.id)
            if not user:
                user = User.new(State, booster.id)
                # Should be unreachable
                await State.db.set_user(user)
            expires_at = user.premium.expires_at
            key = await State.db.get_managed_key(user.id)
            if not key:
                # Should be unreachable
                key = str(uuid.uuid4())
                await State.db.set_premium(user, utils.now(days=31).date(), key_override=key)
                await State.db.set_managed_key(user.id, key)
                continue
            if not expires_at:
                # Should be unreachable
                expires_at = now
            while expires_at < now:
                key.value += 30
            await State.db.set_key(key)

    @loop(seconds=30)
    async def api_status(self):
        await utils.api_status(self.bot, ignore_webhook=True)

    @commands.Cog.listener()
    async def on_ready(self):
        State.is_ready = True
        main_server = State.verify_config.main_server
        # Only allow to run commands in main_server
        State.whitelisted_servers.append(main_server)
        # This bot is legit
        State.protected_servers.clear()
        self.api_status.start()
        self.member_maintenance.start()
        log.info(f'Connected as {self.bot.user} (ID: {self.bot.user.id})')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Bypass react check for existing users
        if not member.guild.id == State.verify_config.main_server:
            return

        await self.fix_name(member)
        if not await utils.verify_user(member, self.role_config):
            welcome_channel = 1517602985495101520
            channel = self.bot.get_channel(welcome_channel)
            if isinstance(channel, discord.TextChannel):
                message = await channel.send(member.mention)
                await message.delete()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.message_id == State.verify_config.verify_message or not payload.guild_id:
            return
        lock = self.locks[f'verify-{payload.user_id}']
        async with lock:
            verify_tasks: set = self.local.setdefault('verify_tasks', set())
            if payload.user_id in verify_tasks:
                return
            verify_tasks.add(payload.user_id)
        guild = self.bot.get_guild(payload.guild_id)
        try:
            if not guild:
                return
            member = guild.get_member(payload.user_id)
            if not member:
                return
            role = guild.get_role(self.role_config.user)
            if not role:
                return
            if not await utils.verify_user(member, self.role_config, force_member=True):
                raise RuntimeError
            channel_ids = [
                1507792963009384569,
                1521195943221919785,
                1507789333287927858
            ]
            messages: list[discord.Message] = []
            for channel_id in channel_ids:
                channel = self.bot.get_channel(channel_id)
                if isinstance(channel, discord.TextChannel):
                    message = await channel.send(member.mention)
                    messages.append(message)
            for message in messages:
                await message.delete()
        finally:
            async with lock:
                verify_tasks.discard(payload.user_id)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if not thread.guild.id == State.verify_config.main_server:
            return
        if not isinstance(thread.parent, discord.ForumChannel):
            # Not a forum thread
            return
        # First message of the thread is the post itself
        message = await thread.fetch_message(thread.id)
        for reaction in (self.emoji.upvote, self.emoji.downvote):
            await message.add_reaction(reaction)

    @commands.Cog.listener()
    async def on_member_update(self, old: discord.Member, member: discord.Member):
        async with self.locks[member.id]:
            if member.guild.id != State.verify_config.main_server:
                return
            if not old.premium_since and member.premium_since:
                user = await State.db.get_user(member.id)
                if not user:
                    user = User.new(State, member.id)
                    await State.db.set_user(user)
                key = str(uuid.uuid4())
                await State.db.set_premium(user, utils.now(days=30).date(), key_override=key)
                await State.db.set_managed_key(member.id, key)
                channel_id = self.bot_config.premium.notification_channel_id
                channel = self.bot.get_channel(channel_id or 0)
                if isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(title=f'{member} is now rich', description=f'{member.mention} thank you for boosting the server. You are now a premium user.')
                    await channel.send(embed=embed)
                
            elif old.premium_since and not member.premium_since:
                user = await State.db.get_user(member.id)
                if not user:
                    # Should be unreachable
                    user = User.new(State, member.id)
                    await State.db.set_user(user)
                await State.db.del_premium(user)
                channel_id = self.bot_config.premium.notification_channel_id
                channel = self.bot.get_channel(channel_id or 0)
                if isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(title=f'{member} is now poor 💩', description=f'{member.mention} your boost expired. You are a regular user now.')
                    await channel.send(embed=embed)
            await self.fix_name(member)
            await utils.verify_user(member, self.role_config)

    @commands.Cog.listener()
    async def on_presence_update(self, old: discord.Member, member: discord.Member):
        async with self.locks[member.id]:
            await utils.verify_user(member, self.role_config)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        invoker = message.author
        if message.interaction_metadata:
            invoker = message.interaction_metadata.user
            invoker = message.guild.get_member(invoker.id)
        if isinstance(invoker, discord.Member):
            if message.channel.id == 1534483688014872636:
                try:
                    await invoker.ban(delete_message_seconds=7 * 24 * 60 * 60, reason='Honeypot')
                    await invoker.unban()
                except discord.HTTPException:
                    pass
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exc: Exception, *args):
        if isinstance(exc, commands.CheckFailure):
            return
        log.error(''.join(traceback.format_exception(exc)))
        
    async def cog_unload(self):
        if self.member_maintenance.is_running():
            self.member_maintenance.stop()
        if self.api_status.is_running():
            self.api_status.stop()
