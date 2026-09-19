import os
import utils
import discord
from discord.ext import commands
from discord import app_commands
from utils.state import State
from utils.commands import command_hook, Cooldown, CooldownCheck as CdCheck, CommandFlags
from utils.enums import CooldownType as CdType, Permissions, PullStatus, KeyType
from utils.modified import ConnectedBot, GuildContext
from utils.models import Premium
from app_types import EmojiConfig, RoleConfig
from ..components import BotInvite, TicketView, URLButton

class Commands(commands.Cog):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot
        with open('config/emoji.json') as file:
            emoji_config = EmojiConfig.model_validate_json(file.read())
        with open('config/role.json') as file:
            self.role_config = RoleConfig.model_validate_json(file.read())
        self.emoji = utils.Emoji(emoji_config)

    @commands.command(aliases=['inv'])
    @command_hook(Cooldown(
        CdCheck(CdType.USER, 5, 60)),
        flags=CommandFlags(bypass_protected=True, bypass_whitelist=True),
        permissions=Permissions.PUBLIC
    )
    async def invite(self, ctx: GuildContext):
        user = await State.db.get_user(ctx.author.id)
        invite_server = State.verify_config.invite_server
        if user and user.auth:
            status = await utils.pull_user(user, invite_server)
            jump = f'https://discord.com/channels/{invite_server}'
            message = ''
            if status is PullStatus.PULLED:
                message = 'You have been added to the invite server.'
            if status is PullStatus.IS_MEMBER:
                message = 'You are a member of the invite server.'
            if message:
                message += ' Click the button below to access the bots.'
                view = URLButton('Go to server', jump)
                await ctx.reply(message, view=view)
                return
        view = BotInvite(ctx.author.id)
        notice = '**YOU NEED TO STAY IN THIS SERVER FOR THE BOT TO WORK**'
        await ctx.send(notice, embed=view.embed, view=view)

    @commands.command(aliases=['tutorial'])
    @command_hook(
        Cooldown(CdCheck(CdType.USER, 1, 3)),
        flags=CommandFlags(bypass_protected=True, bypass_whitelist=True),
        permissions=Permissions.PUBLIC
    )
    async def help(self, ctx: GuildContext):
        tutorial = (
            '# [Tutorial](https://youtu.be/B1axyjXY54c)\n'
            '1. Type .invite in #commands.\n'
            '2. The bot will reply with a message, click on the "🤖 Get Bot" button.\n'
            '3. Now click on "Authorize".\n'
            '4. Authorize your Discord account.\n'
            '> :warning: If you believe we steal Discord accounts, do not use our service.\n'
            '5. Once it shows "Process complete" on the website, close it and check your server list.\n'
            '> :warning: If you was not added to a server, that means you have hit max server limit, and you must leave 1 server, and repeat the process.\n'
            '6. You can find all bots in the server you just got added to.\n'
        )
        await ctx.reply(tutorial)

    @commands.command(aliases=['commands'])
    @command_hook(
        Cooldown(CdCheck(CdType.USER, 1, 3)),
        flags=CommandFlags(bypass_protected=True, bypass_whitelist=True),
        permissions=Permissions.PUBLIC
    )
    async def cmds(self, ctx: GuildContext):
        await ctx.reply('https://api.fluc.lol/assets/v2/commands.png')

    @commands.command()
    @command_hook(permissions=Permissions.ELEVATED)
    async def setup_tickets(self, ctx: GuildContext):
        view = TicketView()
        await ctx.send(embed=view.embed, view=view)

    @commands.command()
    @command_hook(permissions=Permissions.ELEVATED)
    async def send_honeypot(self, ctx: GuildContext):
        embed = discord.Embed(
            title='',
            description=(
                '# DO NOT SEND MESSAGES IN THIS CHANNEL\n'
                'This channel is used to catch spam bots.\n'
                'Any messages sent here will result in a **SOFTBAN**.\n'
                '**THIS IS NOT A JOKE AND IT IS YOUR FINAL WARNING**'
            )
        )
        await ctx.send(embed=embed)

    @app_commands.command()
    @app_commands.describe(code='Code you want to redeem.')
    @command_hook(permissions=Permissions.PUBLIC)
    async def redeem(self, interaction: discord.Interaction, code: str):
        key = await State.db.get_key(code)
        invalid = 'This code is expired or has been used.'
        if not key:
            await interaction.response.send_message(invalid, ephemeral=True)
            return
        if key.redeemed_at:
            await interaction.response.send_message(invalid, ephemeral=True)
            return
        if key.expires_at < utils.now().date():
            await interaction.response.send_message(invalid, ephemeral=True)
            return
        user = await State.db.get_user(interaction.user.id)
        if not user:
            await interaction.response.send_message('You must be a user to redeem keys. Use </db set_auth:1517179899759300909> to become a user.', ephemeral=True)
            return
        if key.type == KeyType.PREMIUM:
            if user.is_premium:
                await interaction.response.send_message('You are a premium user already. Keys cannot be stacked at this moment.')
                return
            member = interaction.user
            if isinstance(member, discord.Member):
                user.premium.key = key.key
                if await State.db.set_user(user):
                    key.redeemed_at = utils.now().date()
                    await State.db.set_key(key)
                    await interaction.response.send_message(f'Premium has been activated until <t:{int(utils.now(days=key.value).timestamp())}:d>', ephemeral=True)
                    await utils.verify_user(member, self.role_config)
                else:
                    await interaction.response.send_message('Could not activate premium.', ephemeral=True)
            else:
                await interaction.response.send_message('Run the command in Fluc server.', ephemeral=True)
        elif key.type is KeyType.RESTORE:
            user.restore_credit += key.value
            key.redeemed_at = utils.now().date()
            if await State.db.set_user(user):
                await State.db.set_key(key)
            else:
                await interaction.response.send_message('Could not activate key. Please contact support.', ephemeral=True)
                return
            await interaction.response.send_message(f'{key.value} restore credits have been added to your account. You now have {user.restore_credit} restore credits.', ephemeral=True)
        else:
            await interaction.response.send_message('This key cannot be redeemed at this moment.', ephemeral=True)
        
    @commands.command()
    @command_hook(permissions=Permissions.ELEVATED)
    async def sync(self, ctx: GuildContext):
        'Dev command. Do not use this.'
        # TODO: Make it sync only main server
        # main_server = State.verify_config.main_server
        # snowflake = discord.Object(main_server)
        # await self.bot.tree.sync(guild=snowflake)
        await self.bot.tree.sync()
        await ctx.message.add_reaction(self.emoji.checkmark)
