__all__ = (
    'Commands',
)

import logging
import discord
import asyncio
import requests
import aiohttp
import utils
from utils.state import State
from utils.modified import ConnectedBot
from utils.commands import command_hook, Cooldown, CooldownCheck as CdCheck, CooldownType as CdType
from utils.enums import Permissions
from discord.ext import commands
from discord import app_commands
from concurrent.futures import ThreadPoolExecutor
from utils.commands import CommandFlags
from utils.models import User, Settings, Premium
from app_types.config import EmojiConfig, MassDMConfig
from .components import SpamMenu, Nitro, Giveaway
from typing import Optional

log = logging.getLogger('fluc')

class Commands(commands.Cog):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot
        with open('config/massdm.json', 'r') as file:
            self.dm_config = MassDMConfig.model_validate_json(file.read())
        super().__init__()

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(delay='Optional delay between messages in seconds.')
    @command_hook(Cooldown(CdCheck(CdType.USER, 6, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def flood(self, interaction: discord.Interaction, delay: int = 0):
        '''Floods the server with messages.'''
        user = await State.db.get_user(interaction.user.id)
        assert user
        await utils.raid(interaction, user, delay_override=delay)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 6, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def invisible(self, interaction: discord.Interaction):
        '''Floods the channel with invisible messages.'''
        u_fff4 = chr(0xfff4)
        content = u_fff4 + '\n' * 1998 + u_fff4
        settings = Settings.new(State, rbot_message=content)
        premium = Premium('0', utils.now(days=360).date())
        user = User.new(State, 0, settings, premium)
        await utils.raid(interaction, user)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 3, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def lag(self, interaction: discord.Interaction):
        '''Lag/crash channel. You are supposed to spam this command.'''
        u_fff4 = chr(0xfff4)
        # Credits to shurikchap for this string
        # 199 is a magic number, do not change
        # I realized that the more mentions you do the less lag things u have to add
        content = f'@everyone @here join discord.gg/fluc for best Discord r4id tools {f'||{u_fff4}||' * 196}'
        settings = Settings.new(State, rbot_message=content)
        premium = Premium('', utils.now(days=360).date())
        user = User.new(State, 0, settings, premium)
        await utils.raid(interaction, user)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @command_hook(
        Cooldown(CdCheck(CdType.USER, 10, 1), CdCheck(CdType.SERVER, 5, 1)),
        flags=CommandFlags(bypass_whitelist=True, bypass_server=True),
        permissions=Permissions.PREMIUM
    )
    async def menu(self, interaction: discord.Interaction):
        '''R4id menu.'''
        user = await State.db.get_user(interaction.user.id)
        view = SpamMenu(interaction, user)
        embed = view.embed
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 6, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def nitro(self, interaction: discord.Interaction):
        '''Sends fake nitro.'''
        user = await State.db.get_user(interaction.user.id)
        view = Nitro(0, user)
        await interaction.response.send_message('Original message was deleted.', ephemeral=True)
        await interaction.followup.send(view=view)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        title='Giveaway title.',
        hosted_by='The person hosting this giveaway.',
        ends_in='When giveaway should end.'
    )
    @command_hook(Cooldown(CdCheck(CdType.USER, 6, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def giveaway(self, interaction: discord.Interaction, title: Optional[str] = None, hosted_by: Optional[str] = None, ends_in: Optional[str] = None, ):
        '''Sends fake giveaway.'''
        user = await State.db.get_user(interaction.user.id)
        assert user
        if not user.is_premium:
            title = None
            hosted_by = None
            ends_in = None
        expires = utils.parse_datetime(ends_in or '2d')
        view = Giveaway(0, user, title, hosted_by, expires or utils.now(days=2))
        await interaction.response.send_message('Original message was deleted.', ephemeral=True)
        await interaction.followup.send(embed=view.embed, view=view)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @command_hook(Cooldown(CdCheck(CdType.USER, 3, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def can_flood(self, interaction: discord.Interaction):
        '''Checks whether the current channel can be flooded.'''
        can_flood = utils.can_flood(interaction)
        text = '{} This channel {} be flooded.'
        if can_flood:
            text = text.format(':white_check_mark:', '**CAN**')
        else:
            text = text.format(':x:', '**CANNOT**')
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user='User to ghostping.', everyone='Whether to ping @everyone.', here='Whether to ping @here.')
    @command_hook(Cooldown(CdCheck(CdType.USER, 6, 2), CdCheck(CdType.SERVER, 5, 5)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def ghostping(self, interaction: discord.Interaction, user: Optional[discord.User] = None, everyone: Optional[bool] = False, here: Optional[bool] = False):
        '''Ghostpings a member.'''
        async def send():
            message = await interaction.followup.send(content, allowed_mentions=discord.AllowedMentions.all(), wait=True)
            await interaction.followup.delete_message(message.id)

        if not utils.can_flood(interaction):
            await interaction.response.send_message('I do not have permissions to ghostping in this channel.', ephemeral=True)
            return
        content = ''
        if everyone:
            content += ' @everyone'
        if here:
            content += ' @here'
        if user:
            content += f' {user.mention}'
        if not content:
            await interaction.response.send_message('Who am I supposed to ghostping?', ephemeral=True)
            return
        await interaction.response.send_message(content, delete_after=0.1, allowed_mentions=discord.AllowedMentions.all())
        for _ in range(5):
            await send()

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user='User to mass DM.')
    @command_hook(Cooldown(CdCheck(CdType.USER, 120, 1), CdCheck(CdType.GLOBAL, 10, 1)), flags=CommandFlags(bypass_whitelist=True, bypass_server=True))
    async def massdm(self, interaction: discord.Interaction, user: discord.User):
        '''Sends a ton of DMs to user.'''
        stop = []
        tokens = self.dm_config.tokens
        user_ = await State.db.get_user(interaction.user.id)
        assert user_
        if len(tokens) <= 3:
            await interaction.response.send_message('Missing tokens.')
            return
        async with aiohttp.ClientSession() as session:
            async def open_dm(token: str):
                headers = {
                    'authorization': f'Bot {token}'
                }
                data = {
                    'recipient_id': user.id
                }
                async with session.post('https://discord.com/api/users/@me/channels', json=data, headers=headers) as response:
                    if not response.ok:
                        return
                    data = await response.json()
                    return data['id']

            async def dm(token: str, channel_id: int):
                headers = {
                    'authorization': f'Bot {token}'
                }
                data = {
                    'content': user_.settings.rbot_message,
                    'tts': user_.settings.rbot_tts,
                    'allowed_mentions': {
                        'parse': [
                            'everyone',
                            'users',
                            'roles'
                        ]
                    }
                }
                async with session.post(f'https://discord.com/api/channels/{channel_id}/messages', json=data, headers=headers) as response:
                    if not response.ok:
                        # Not ratelimited
                        if not response.status == 429:
                            stop.append(channel_id)

            url = 'https://discord.com/api/guilds/{}/members/{}'
            url = url.format(self.dm_config.server_id, user.id)
            session.headers['authorization'] = f'Bot {self.dm_config.manager_token}'
            response = await session.get(url)
            if not response.ok:
                # Most likely, I cannot be asked to check every situation
                content = 'User not in victim server.'
                if self.dm_config.invite:
                    content += f' Make sure target join this server: {self.dm_config.invite}'
                cmd = State.get_command('massdm')
                if cmd and cmd.cooldown:
                    cmd.cooldown.remove_cooldown(interaction.user.id)
                await interaction.response.send_message(content, ephemeral=True)
                return
            await interaction.response.send_message('Creating DM channels...', ephemeral=True)
            channel_ids = {}
            for token in tokens:
                channel_id = await open_dm(token)
                if channel_id:
                    channel_ids[token] = channel_id
            await interaction.followup.send(f'{len(channel_ids)} bots DMing {user.mention}', ephemeral=True)
            amount = 25
            if user_.is_premium:
                amount *= 2
            for _ in range(amount):
                for token, channel_id in channel_ids.items():
                    if not channel_id in stop:
                        asyncio.create_task(dm(token, channel_id))
                        await asyncio.sleep(0.05)

    @app_commands.command()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @command_hook(permissions=Permissions.ELEVATED)
    async def sync(self, interaction: discord.Interaction):
        'Dev command. Do not use this.'
        await interaction.response.defer(thinking=True, ephemeral=True)
        await self.bot.tree.sync()
        await interaction.followup.send('Synced', ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            return
        log.error(error)
