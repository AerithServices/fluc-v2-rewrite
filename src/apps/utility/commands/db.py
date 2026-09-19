import discord
import dateparser
import json
import logging
import utils
import uuid
from datetime import datetime
from discord import app_commands
from utils.commands import command_hook, Permissions
from utils.enums import RowStatus
from utils.state import State
from utils.enums import PullStatus, PunishmentType, KeyType
from utils.models import User, Premium, Blacklist, Key
from discord.ext import commands
from utils.modified import ConnectedBot
from app_types import WebsiteConfig, RoleConfig, EmojiConfig
from typing import Optional, Literal

log = logging.getLogger('fluc')

class DatabaseCommands(commands.GroupCog, name='db'):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot
        self.dateparser_settings = {
            'TIMEZONE': 'UTC',
            # Apply timezone
            'RETURN_AS_TIMEZONE_AWARE': True,
            'TO_TIMEZONE': 'UTC',
            # Prefer dates from future
            'PREFER_DATES_FROM': 'future',
            'RELATIVE_BASE': utils.now()
        }
        # Known issue
        self.dateparser = lambda date_string: dateparser.parse(date_string, settings=self.dateparser_settings) # pyright: ignore[reportArgumentType]
        with open('config/website.json') as file:
            self.website_config = WebsiteConfig.model_validate_json(file.read())
        with open('config/role.json') as file:
            self.role_config = RoleConfig.model_validate_json(file.read())
        with open('config/emoji.json') as file:
            emoji_config = EmojiConfig.model_validate_json(file.read())
        with open('config/punishments.json') as file:
            self.punishments: dict[str, dict] = json.load(file)
        self.emoji = utils.Emoji(emoji_config)

    @app_commands.command()
    @app_commands.describe(
        user='User to manage',
        premium_until='Premium expiration date.',
        blacklisted_until='Blacklist expiration date.',
        is_super='Whether the user should be a super user.'
    )
    @command_hook(permissions=Permissions.ELEVATED)
    async def set_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        premium_until: Optional[app_commands.Range[str, 0, 20]] = None,
        blacklisted_until: Optional[app_commands.Range[str, 0, 20]] = None,
        is_super: Optional[bool] = None,
        is_limited: Optional[bool] = None
    ):
        '''Updates a user.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            _user = User.new(State, user.id)

        if premium_until:
            premium_expires = self.dateparser(premium_until)
            if premium_expires:
                key = Key(
                    str(uuid.uuid4()),
                    utils.now().date(),
                    utils.now(days=30).date(),
                    (premium_expires - utils.now()).days,
                    KeyType.PREMIUM,
                    utils.now().date()
                )
                _user.premium = Premium(key.key, premium_expires.date())
                await State.db.set_key(key)
        elif premium_until and utils.is_none(premium_until):
            _user.premium.expires_at = None
        if blacklisted_until:
            blacklist_expires = self.dateparser(blacklisted_until)
            if blacklist_expires:
                _user.blacklist = Blacklist(blacklist_expires.date())
        elif blacklisted_until and utils.is_none(blacklisted_until):
            _user.blacklist.expires_at = None

        invoker = await State.db.get_user(interaction.user.id)
        assert invoker
        if is_super is not None:
            if not invoker.is_owner and not _user.is_owner:
                _user.flags.is_super = is_super
        if is_limited is not None:
            if not _user.is_elevated:
                _user.flags.limited = is_limited

        rows = await State.db.set_user(_user)
        if rows is RowStatus.NOT_UPDATED:
            await interaction.response.send_message(f'{self.emoji.crossmark} User was `not updated`.')
        elif rows is RowStatus.UPDATED:
            await interaction.response.send_message(f'{self.emoji.checkmark} User `updated`.')
        elif rows is RowStatus.CREATED:
            await interaction.response.send_message(f'{self.emoji.checkmark} User `created`.')
        member = interaction.guild.get_member(user.id) # pyright: ignore[reportOptionalMemberAccess]
        if member:
            await utils.verify_user(member, self.role_config)

    @app_commands.command()
    @app_commands.describe(user='User to get.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def get_user(self, interaction: discord.Interaction, user: discord.User):
        '''Shows info about a user.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        auth = _user.auth
        embed = discord.Embed(
            title=auth and auth.username or (user.name or user.id),
            description='',
            color=discord.Color.blue()
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.set_thumbnail(url=auth and auth.avatar or (user.avatar and user.avatar.url or None))
        premium_active_until = 'No Data'
        blacklist_active_until = 'No Data'
        if _user.is_premium and _user.premium.expires_at:
            premium_active_until = _user.premium.expires_at.isoformat()
        if _user.is_blacklisted and _user.blacklist.expires_at:
            blacklist_active_until = _user.blacklist.expires_at.isoformat()
        is_elevated_emoji = self.emoji.crossmark
        if _user.is_elevated:
            is_elevated_emoji = self.emoji.checkmark
        is_verified_emoji = self.emoji.crossmark
        if _user.auth:
            is_verified_emoji = self.emoji.checkmark
        is_limited_emoji = self.emoji.crossmark
        if _user.is_limited:
            is_limited_emoji = self.emoji.checkmark
        embed.add_field(
            name='Status',
            value=(
                f'Premium Active Until: `{premium_active_until}`\n'
                f'Blacklisted Until: `{blacklist_active_until}`\n'
                f'Verified: {is_verified_emoji}\n'
                f'Elevated: {is_elevated_emoji}\n'
                f'Limited: {is_limited_emoji}'
            )
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.describe(user='User to delete.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def del_user(self, interaction: discord.Interaction, user: discord.User):
        '''Deletes a user.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        if _user.is_elevated:
            if _user.is_owner:
                await interaction.response.send_message(f'{self.emoji.crossmark} This user `cannot be deleted`.\nPlease delete this user manually by logging onto the database.')
                return
            invoker = await State.db.get_user(interaction.user.id)
            assert invoker
            if not invoker.is_owner:
                await interaction.response.send_message(f'{self.emoji.crossmark} You `cannot delete` this user.')
                return
        if await State.db.del_user(user.id):
            # Guild cannot be none, command cannot be ran in private channels
            member = interaction.guild.get_member(user.id) # pyright: ignore[reportOptionalMemberAccess]
            if member:
                keep = []
                for role in member.roles:
                    if not role.is_assignable():
                        # Prob booster role
                        keep.append(role)
                await member.edit(roles=keep)
            await interaction.response.send_message(f'{self.emoji.checkmark} User `deleted`.')
        else:
            await interaction.response.send_message(f'{self.emoji.crossmark} User was `not deleted`.')
        
    @app_commands.command()
    @command_hook(permissions=Permissions.PUBLIC)
    async def set_auth(self, intreaction: discord.Interaction):
        '''Sets auth for a user.'''
        website = self.website_config.domain
        await intreaction.response.send_message(f'{self.emoji.checkmark} Please login on {website} and authorize.')

    @app_commands.command()
    @app_commands.describe(user='User to check.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def get_auth(self, interaction: discord.Interaction, user: discord.User):
        '''Shows info about user's auth.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        auth = _user.auth
        if not auth:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not authorized`.')
            return
        embed = discord.Embed(
            title=auth.username,
            description='',
            color=discord.Color.blue()
        )
        date_info = auth.expires.date()
        embed.add_field(
            name='Info',
            value=(
                f'Username: `{auth.username}`\n'
                f'Avatar: `{auth.avatar}`\n'
                'Access Token: `****`\n'
                f'Token Type: `{auth.token_type}`\n'
                f'Scope: `{auth._scope}`\n'
                f'Refresh Token: `****`\n'
                f'Expires: `{date_info.isoformat()}`'
            )
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.describe(user='User to edit.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def del_auth(self, interaction: discord.Interaction, user: discord.User):
        '''Deletes auth from a user.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        auth = _user.auth
        if not auth:
            await interaction.response.send_message(f'{self.emoji.crossmark} This user has `not authorized`.')
            return
        if _user.is_owner:
            await interaction.response.send_message((
                'I `cannot modify this user`.\n'
                'Please modify this user manually by logging onto the database.')
            )
            return
        if await State.db.del_auth(user.id):
            await interaction.response.send_message(f'{self.emoji.checkmark} Auth has been `deleted`.')
        else:
            await interaction.response.send_message(f'{self.emoji.crossmark} Auth was `not deleted`.')

    @app_commands.command()
    @app_commands.describe(
        user='User to update.',
        premium_until='Expiration date of premium.',
        extend='Whether to extend premium instead of overwriting it.'
    )
    @command_hook(permissions=Permissions.ELEVATED)
    async def set_premium(self,
        interaction: discord.Interaction,
        user: discord.User,
        premium_until: app_commands.Range[str, 0, 20],
        extend: Optional[bool] = False
    ):
        '''Update user's premium expiration date.'''
        # Dummy value that will be overwriten later
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        if utils.is_none(premium_until):
            premium_expires = None    
        else:
            parsed = self.dateparser(premium_until)
            if not parsed:
                await interaction.response.send_message(f'{self.emoji.crossmark} `Could not parse` premium expiration date.')
                return
            expires_at = _user.premium.expires_at
            if extend and expires_at:
                extend_by = (parsed - utils.now()).days
                premium_expires = utils.now(days=extend_by).date()
            else:
                premium_expires = parsed.date()
        rows = await State.db.set_premium(_user, premium_expires)
        if rows is RowStatus.UPDATED:
            member = interaction.guild.get_member(user.id) # pyright: ignore[reportOptionalMemberAccess]
            if member:
                role = discord.Object(self.role_config.premium)
                await member.add_roles(role)
            await interaction.response.send_message(f'{self.emoji.checkmark} Premium status `updated`.')
        else:
            # Can be only RowStatus.NOT_UPDATED
            await interaction.response.send_message(f'{self.emoji.crossmark} Premium status `not updated`.')

    @app_commands.command()
    @app_commands.describe(user='User to update.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def del_premium(self, interaction: discord.Interaction, user: discord.User):
        '''Removes premium from a user.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        if _user.is_elevated:
            if _user.is_owner:
                await interaction.response.send_message(
                    'This user `cannot be updated`.\n'
                    'Please update this user manually on the database.'
                )
                return
            if _user.flags.is_super:
                invoker = await State.db.get_user(interaction.user.id)
                assert invoker
                if not invoker.is_owner:
                    await interaction.response.send_message(f'{self.emoji.crossmark} You `cannot update` this user.')
                    return
        if await State.db.del_premium(_user):
            member = interaction.guild.get_member(user.id) # pyright: ignore[reportOptionalMemberAccess]
            if member:
                role = discord.Object(self.role_config.premium)
                await member.remove_roles(role)
            await interaction.response.send_message(f'{self.emoji.checkmark} Premium status has been `updated`.')
        else:
            await interaction.response.send_message(f'{self.emoji.crossmark} Premium status was `not updated`.')

    @app_commands.command()
    @app_commands.describe(
        type='Type of key.',
        expires='Key experity date.',
        value='Amount of days of promotion/amount of credits.',
        amount='Amount of keys to generate.'
    )
    @command_hook(permissions=Permissions.MOD)
    async def set_key(self, intreaction: discord.Interaction, type: Literal['PREMIUM', 'RESTORE'], expires: str = '1 year', value: int = 31, amount: int = 1):
        '''Generates keys.'''
        keys = []
        amount = max(min(amount, 10), 1)
        value = max(value, 1)
        await intreaction.response.defer()
        expires_at = utils.parse_datetime(expires)
        if not expires_at:
            await intreaction.followup.send('Failed to parse `expires`.')
            return
        for _ in range(amount):
            key = Key(
                str(uuid.uuid4()),
                utils.now().date(),
                expires_at.date(),
                value,
                KeyType[type],
                None
            )
            status = await State.db.set_key(key)
            if status is RowStatus.CREATED:
                keys.append(key.key)
        generated = len(keys)
        await intreaction.followup.send(f'Generated {generated}x key{'s' if generated > 1 else ''}.')
        await intreaction.followup.send('||\n' + '\n'.join(keys) + '\n||', ephemeral=True)

    @app_commands.command()
    @app_commands.describe(key='Key to delete.')
    @command_hook(permissions=Permissions.MOD)
    async def del_key(self, interaction: discord.Interaction, key: str):
        '''Invalidates/deletes a key'''
        if await State.db.del_key(key):
            await interaction.response.send_message('Key `deleted`.')
        else:
            await interaction.response.send_message('Key `not deleted`.')

    @app_commands.command()
    @app_commands.describe(
        user='User to update.',
        blacklisted_until='Expiration date of blacklist.'
    )
    @command_hook(permissions=Permissions.MOD)
    async def set_blacklist(self,
        interaction: discord.Interaction,
        user: discord.User,
        blacklisted_until: app_commands.Range[str, 0, 20]
    ):
        '''Update user's blacklist expiration date.'''
        if utils.is_none(blacklisted_until):
            blacklist_expires = None    
        else:
            blacklist_expires = self.dateparser(blacklisted_until)
        if not blacklist_expires:
            await interaction.response.send_message(f'{self.emoji.crossmark} `Could not parse` blacklist expiration date.')
            return
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        if _user.is_elevated:
            await interaction.response.send_message(f'{self.emoji.crossmark} This user `cannot be blacklisted`.')
            return
        rows = await State.db.set_blacklist(user.id, blacklist_expires.date())
        if rows is RowStatus.UPDATED:
            member = interaction.guild.get_member(user.id) # pyright: ignore[reportOptionalMemberAccess]
            if member:
                role = discord.Object(self.role_config.blacklisted)
                await member.edit(roles=[role])
            await interaction.response.send_message(f'{self.emoji.checkmark} Blacklist status `updated`.')
        else:
            # Can be only RowStatus.NOT_UPDATED
            await interaction.response.send_message(f'{self.emoji.crossmark} Blacklist status `not updated`.')

    @app_commands.command()
    @app_commands.describe(user='User to update.')
    @command_hook(permissions=Permissions.MOD)
    async def del_blacklist(self, interaction: discord.Interaction, user: discord.User):
        '''Removes blacklist from a user.'''
        _user = await State.db.get_user(user.id)
        if not _user:
            await interaction.response.send_message(f'{self.emoji.crossmark} User `not found`.')
            return
        if _user.is_elevated:
            if _user.is_owner:
                await interaction.response.send_message(
                    'This user `cannot be updated`.\n'
                    'Please update this user manually on the database.'
                )
                return
            if _user.flags.is_super:
                invoker = await State.db.get_user(interaction.user.id)
                assert invoker
                if not invoker.is_owner:
                    await interaction.response.send_message(f'{self.emoji.crossmark} You `cannot update` this user.')
                    return
        if await State.db.del_blacklist(user.id):
            member = interaction.guild.get_member(user.id) # pyright: ignore[reportOptionalMemberAccess]
            if member:
                await utils.verify_user(member, self.role_config)
            await interaction.response.send_message(f'{self.emoji.checkmark} Blacklist status has been `updated`.')
        else:
            await interaction.response.send_message(f'{self.emoji.crossmark} Blacklist status was `not updated`.')

    @app_commands.command()
    @app_commands.describe(punishment_id='ID of punishment.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def get_punishment(self, interaction: discord.Interaction, punishment_id: int):
        punishment = await State.db.get_punishment(punishment_id)
        if not punishment:
            await interaction.response.send_message(f'{self.emoji.crossmark} Punishment `not found`.')
            return
        for data in self.punishments.values():
            if data.get('id') == punishment.action_id:
                action = data.get('text', 'No data')
                break
        else:
            action = 'No data'
        description = (
            f'Affected user: <@{punishment.user_id}>\n'
            f'Offended by: <@{punishment.moderator_id}>\n'
            f'Action: `{action}.`\n'
            f'Executed Action: `{PunishmentType(punishment.executed_action_id).name}`\n'
            f'Done at: <t:{int(punishment.done_at.timestamp())}:R>'
        )
        embed = discord.Embed(
            title=f'Punishment #{punishment_id}',
            description=description
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @app_commands.describe(punishment_id='ID of punishment.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def del_punishment(self, interaction: discord.Interaction, punishment_id: int):
        if await State.db.del_punishment(punishment_id):
            await interaction.response.send_message(f'{self.emoji.checkmark} Punishment `deleted`.')
        else:
            await interaction.response.send_message(f'{self.emoji.crossmark} Punishment `not deleted`.')

    @app_commands.command()
    @app_commands.describe(member='Member to verify.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def verify_user(self, interaction: discord.Interaction, member: discord.Member):
        '''Verifies a member and update their roles.'''
        await utils.verify_user(member, self.role_config)
        await interaction.response.send_message(f'{self.emoji.checkmark} User `verified`.')

    @app_commands.command()
    @app_commands.describe(user='User to pull.', server_id='ID of server.')
    @command_hook(permissions=Permissions.ELEVATED)
    async def pull(self, interaction: discord.Interaction, user: discord.User, server_id: str):
        '''Pulls user to specified server.'''
        user_ = await State.db.get_user(user.id)
        if not user_:
            await interaction.response.send_message('User `doesn\'t exist`.')
            return
        try:
            if await utils.pull_user(user_, int(server_id)) is PullStatus.PULLED:
                await interaction.response.send_message('User `pulled`.')
            else:
                await interaction.response.send_message('User was `not pulled`.')
        except AssertionError:
            await interaction.response.send_message('User `not authorized`')
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            return
        log.error(error)
