import discord
import datetime
import json
import utils
import os
from discord.ext import commands
from utils.state import State
from utils.modified import ConnectedBot, GuildInteraction
from utils.models import Punishment, User
from utils.core import Emoji
from utils.enums import PunishmentType
from app_types.config import EmojiConfig, RoleConfig
from discord import app_commands
from typing import cast, Literal, Optional, Union

with open('config/punishments.json') as file:
    punishments = json.load(file)

all_punishments = []
for punishment in punishments.copy():
    # Basically converts all keys to lowercase
    if not punishment.islower():
        data = punishments.pop(punishment)
        punishment = punishment.lower()
        punishments[punishment] = data
    if punishment == 'default':
        continue
    result = ''
    separate = punishment.split('/')
    for item in separate:
        result += item.title() + '/'
    result = result.removesuffix('/')
    all_punishments.append(result)

# PROPERTY OF MR. QX OD DO NOT TOUCH OR YOU WILL BE KILLED
class ModCommands(commands.GroupCog, name='mod'):
    def __init__(self, bot: ConnectedBot):
        self.bot = bot
        with open('config/role.json') as file:
            self.roles = RoleConfig.model_validate_json(file.read())

    async def can_punish(
        self,
        member: discord.Member,
        target: Union[discord.Member, discord.User]
    ) -> bool:
        user = await State.db.get_user(member.id)
        target_user = await State.db.get_user(target.id)
        if member.id in State.owner_ids:
            return target.id not in State.owner_ids
        if user and user.is_elevated:
            return not target_user or not target_user.is_elevated
        if any(role.id == self.roles.moderator for role in member.roles):
            if not isinstance(target, discord.Member):
                return True
            return member.top_role > target.top_role
        return False   

    @app_commands.command()
    @app_commands.describe(
        user='User to offend.',
        action='Action by user/reason.',
        message_id='Message ID referring to action by user.',
        message_content='Display message content in user DMs.'
    )
    async def offend(
        self,
        interaction: discord.Interaction,
        user: Union[discord.User, discord.Member],
        action: Literal[*all_punishments], # pyright: ignore[reportInvalidTypeForm]
        message_id: Optional[str] = None,
        message_content: Optional[bool] = True
    ):
        '''Use this command when someone breaks server rules.'''
        interaction = cast(GuildInteraction, interaction)
        if isinstance(message_id, int) or message_id and message_id.isdigit():
            # Doesn't matter in this context
            message_id = int(message_id) # pyright: ignore[reportAssignmentType]
        else:
            message_id = None
        if not await self.can_punish(interaction.user, user):
            return
        await interaction.response.defer(thinking=True)
        user_db = await State.db.get_user(user.id)
        punishment_data = punishments[action.lower()]
        text = punishment_data['text']
        try:
            # Ignore errors
            message = await interaction.channel.fetch_message(message_id or 0) # type: ignore
            await message.delete()
        except discord.HTTPException:
            # NotFound in most cases
            message = None
        dismiss_days = punishments['default']['punishment_dismiss_days']
        dismiss_before = utils.now(days=dismiss_days, reverse=True)
        punishment_history = await State.db.get_punishments(user.id)
        history = []
        for punishment_old in punishment_history:
            if punishment_old.done_at > dismiss_before:
                history.append(punishment_old)
        try:
            action_index = punishment_data['punishments'][len(history)]
        except IndexError:
            action_index = 4
        data = [0, interaction.user.id, user.id, punishment_data['id'], action_index]
        if not message:
            data.append(utils.now())
        else:
            data.append(message.created_at)
        punishment = Punishment(*data)
        action = PunishmentType(action_index)
        action_data = {}
        todos = []
        if action is PunishmentType.WARN:
            action_data['title'] = 'Warning'
            action_data['color'] = discord.Color.yellow()
        if action is PunishmentType.MUTE:
            action_data['title'] = 'Timeout'
            action_data['color'] = discord.Color.yellow()
            timeouts = 0
            for punishment_old in history:
                if punishment_old.action_id is PunishmentType.MUTE:
                    timeouts += 1
            duration = {}
            match timeouts:
                case 0:
                    duration['minutes'] = 10
                case 1:
                    duration['hours'] = 1
                case 2:
                    duration['days'] = 1
                case _:
                    duration['days'] = min(timeouts * 2, 28)
            timed_out_until = utils.now(**duration)
            if isinstance(user, discord.Member):
                await user.edit(timed_out_until=timed_out_until, reason=text)
        if action is PunishmentType.KICK:
            action_data['title'] = 'Kicked'
            action_data['color'] = discord.Color.red()
            if isinstance(user, discord.Member):
                todos.append(user.kick(reason=text))
        if action is PunishmentType.BAN:
            async def ban():
                try:
                    await user.send('You have been banned.\n-# Our mistake? You can appeal this ban in [our appeal server](<https://discord.gg/x3JtwWwX6h>)')
                finally:
                    await interaction.guild.ban(user, reason=text, delete_message_days=0)
            action_data['title'] = 'Banned'
            action_data['color'] = discord.Color.red()
            todos.append(ban())
        if action is PunishmentType.LIMIT:
            user_db = user_db or User.new(State, user.id)
            action_data['title'] = 'Limited'
            action_data['color'] = discord.Color.red()
            user_db.flags.is_super = False
            user_db.flags.limited = True
            await State.db.set_user(user_db)
            if isinstance(user, discord.Member):
                todos.append(utils.verify_user(user, self.roles))
        if action is PunishmentType.BLACKLIST:
            if not user_db:
                user_db = User.new(State, user.id)
                await State.db.set_user(user_db)
            action_data['title'] = 'Blacklisted'
            # Black
            action_data['color'] = discord.Color.from_str('#000')
            await State.db.set_blacklist(user.id, utils.now(days=30))
        description = f'{user.mention} you broke rules for: **' + text + '.**'
        content = '`[unavailable content]`'
        if message:
            description += '\nYour message has been removed because it violated our community rules.'
            if message.content and message_content:
                if 'csam' not in text.lower() and 'gore' not in text.lower():
                    content_split = message.content[:1000].splitlines()
                    content = '> '.join(content_split)
        description += f'\n**Message:**\n> {content}'
        description += '\nRepeated violations may result in permanent removal from the server.'
        case_id = await State.db.set_punishment(punishment)
        embed = discord.Embed(
            title=action_data.get('title', 'Punishment'),
            color=action_data.get('color'),
            description=description
        )
        embed.add_field(name='Case ID:', value=f'#{case_id}')
        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            assert embed.description
            old = embed.description
            embed.description = old.replace(content, '`[unavailable content`')
            if not isinstance(interaction.channel, (discord.ForumChannel, discord.CategoryChannel)):
                assert interaction.channel
                await interaction.channel.send(embed=embed)
            embed.description = old
        finally:
            for todo in todos:
                await todo
        WEBHOOK_TOKEN = os.getenv('PUNISHMENT_WEBHOOK_TOKEN', '')
        WEBHOOK_ID = os.getenv('PUNISHMENT_WEBHOOK_ID', '')
        url = f'https://discord.com/api/webhooks/{WEBHOOK_ID}/{WEBHOOK_TOKEN}'
        webhook = discord.Webhook.from_url(url, client=self.bot)
        try:
            await webhook.send(embed=embed)
        except discord.HTTPException:
            pass
        await interaction.followup.send('Punishment executed.', ephemeral=True)
        # await interaction.response.send_message('Punishment executed')

    # user_group = app_commands.Group(name='user', description='User management commands')
    # role_group = app_commands.Group(name='role', description='Role management commands')
    # channel_group = app_commands.Group(name='channel', description='Channel management commands')

    # def __init__(self, bot: ConnectedBot) -> None:
    #     self.bot = bot
    #     with open('config/emoji.json') as file:
    #         emoji_config = EmojiConfig.model_validate_json(file.read())
    #     self.emoji = Emoji(emoji_config)

    # @user_group.command(name='kick', description='Kick a user')
    # @app_commands.describe(user='The user to kick', reason='Reason for the kick', dm='DM kick details to user')
    # async def user_kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = 'No reason provided', dm: bool = False):
    #     if not cast(discord.Member, interaction.user).guild_permissions.kick_members:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `kick_members` permission',
    #             color=discord.Color.from_rgb(250,10,10)
    #             )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     if dm:
    #         embed = discord.Embed(
    #             title=f'You have been kicked from **{interaction.guild.name}**', # pyright: ignore[reportOptionalMemberAccess]
    #             color=discord.Color.from_rgb(250,10,10)
    #             )
    #         embed.add_field(name='Reason', value=reason)
    #         embed.add_field(name='Administrator', value=f'<@{interaction.user.id}> - {interaction.user.name}')
    #         try:
    #             await user.send(embed=embed)
    #         except discord.Forbidden:
    #             pass

    #     try:
    #         await user.kick(reason=reason)
    #         embed = discord.Embed(
    #             title='User kicked',
    #             description=f'{self.emoji.checkmark} <@{user.id}> - {user.name} has been kickedd',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #         embed.add_field(name='Reason', value=reason)
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `kick_members` permission or user is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @user_group.command(name='ban', description='Ban a user')
    # @app_commands.describe(user='The user to ban', delete_messages_days = 'Delete messages sent in the past days.', reason='Reason for the ban', dm='DM ban details to user')
    # async def user_ban(self, interaction: discord.Interaction, user: discord.User, delete_messages_days: app_commands.Range[int, 0, 7] = 0, reason: str = 'No reason provided', dm: bool = False):
    #     interaction = cast(GuildInteraction, interaction)
    #     if not cast(discord.Member, interaction.user).guild_permissions.ban_members:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `ban_members` permission',
    #             color=discord.Color.from_rgb(250,10,10)
    #             )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     if dm:
    #         embed = discord.Embed(
    #             title=f'You have been banned in **{interaction.guild.name}**', # pyright: ignore[reportOptionalMemberAccess]
    #             color=discord.Color.from_rgb(250,10,10)
    #             )
    #         embed.add_field(name='Reason', value=reason)
    #         embed.add_field(name='Administrator', value=f'<@{interaction.user.id}> - {interaction.user.name}')
    #         try:
    #             await user.send(embed=embed)
    #         except discord.Forbidden:
    #             pass

    #     try:
    #         await interaction.guild.ban(user, reason=reason, delete_message_days=delete_messages_days)
    #         embed = discord.Embed(
    #             title='User banned',
    #             description=f'{self.emoji.checkmark} <@{user.id}> - {user.name} has been banned',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #         embed.add_field(name='Reason', value=reason)
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `ban_members` permission or user is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @user_group.command(name='unban', description='Unban a user')
    # @app_commands.describe(user='The user to unban')
    # async def user_unban(self, interaction: discord.Interaction, user: discord.User):
    #     interaction = cast(GuildInteraction, interaction)
    #     if not cast(discord.Member, interaction.user).guild_permissions.ban_members:
    #         embed = discord.Embed(title='Forbidden', description=f'{self.emoji.crossmark} You are missing `ban_members` permission', color=discord.Color.from_rgb(250,10,10))
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await interaction.guild.unban(user)
    #         embed = discord.Embed(
    #             title='User unbanned',
    #             description=f'{self.emoji.checkmark} <@{user.id}> - {user.name} has been unbanned',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `ban_members` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @user_group.command(name='timeout', description='Timeout a user')
    # @app_commands.describe(user='The user to timeout', reason='Reason for the timeout', duration='Duration in minutes', dm='DM timeout details to user')
    # async def user_timeout(self, interaction: discord.Interaction, user: discord.Member, duration: int = 10, reason: str = 'No reason provided', dm: bool = False):
    #     if not cast(discord.Member, interaction.user).guild_permissions.moderate_members:
    #         embed = discord.Embed(title='Forbidden', description=f'{self.emoji.crossmark} You are missing `moderate_members` permission', color=discord.Color.from_rgb(239, 57, 57))
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     if dm:
    #         dm_embed = discord.Embed(title=f'You have been timed out in **{interaction.guild.name}**', color=discord.Color.from_rgb(239, 57, 57)) # pyright: ignore[reportOptionalMemberAccess]
    #         dm_embed.add_field(name='Reason', value=reason)
    #         dm_embed.add_field(name='Duration', value=f'{duration} minutes')
    #         dm_embed.add_field(name='Administrator', value=f'<@{interaction.user.id}> - {interaction.user.name}')
    #         try:
    #             await user.send(embed=dm_embed)
    #         except discord.Forbidden:
    #             pass

    #     try:
    #         await user.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=duration), reason=reason)
    #         embed = discord.Embed(
    #             title='User timed out',
    #             description=f'{self.emoji.checkmark} <@{user.id}> - {user.name} has been timed out for {duration} minutes',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #         embed.add_field(name='Reason', value=reason)
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `moderate_members` permission or user is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @user_group.command(name='untimeout', description='Remove a timeout from a user')
    # @app_commands.describe(user='The user to untimeout')
    # async def user_untimeout(self, interaction: discord.Interaction, user: discord.Member):
    #     if not cast(discord.Member, interaction.user).guild_permissions.moderate_members:
    #         embed = discord.Embed(title='Forbidden',
    #         description=f'{self.emoji.crossmark} You are missing `moderate_members` permission',
    #         color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await user.timeout(None)
    #         embed = discord.Embed(
    #             title='Timeout removed',
    #             description=f'{self.emoji.checkmark} <@{user.id}> - {user.name} timeout has been removed',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `moderate_members` permission or user is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @user_group.command(name='rename', description='Rename a user')
    # @app_commands.describe(user='The user to rename', new_name='The name user will be renamed to')
    # async def user_rename(self, interaction: discord.Interaction, user: discord.Member, new_name: str):
    #     if not cast(discord.Member, interaction.user).guild_permissions.moderate_members:
    #         embed = discord.Embed(title='Forbidden',
    #         description=f'{self.emoji.crossmark} You are missing `moderate_members` permission',
    #         color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await user.edit(nick=new_name)
    #         embed = discord.Embed(
    #             title='User renamed',
    #             description=f'{self.emoji.checkmark} <@{user.id}> - {user.name} has been renamed into `{new_name}`',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `moderate_members` permission or user is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)
   


    # @role_group.command(name='add', description='Add a role to a user')
    # @app_commands.describe(user='The user to add a role to', role='The role to add')
    # async def role_add(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    #     if not cast(discord.Member, interaction.user).guild_permissions.manage_roles:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `manage_roles` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await user.add_roles(role)
    #         embed = discord.Embed(
    #             title='Role added',
    #             description=f'{self.emoji.checkmark} <@&{role.id}> has been added to <@{user.id}>',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `manage_roles` permission or role is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @role_group.command(name='remove', description='Remove a role from a user')
    # @app_commands.describe(user='The user to remove a role from', role='The role to remove')
    # async def role_remove(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    #     if not cast(discord.Member, interaction.user).guild_permissions.manage_roles:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `manage_roles` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await user.remove_roles(role)
    #         embed = discord.Embed(
    #             title='Role removed',
    #             description=f'{self.emoji.crossmark} <@&{role.id}> has been removed from <@{user.id}>',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `manage_roles` permission or role is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)



    # @channel_group.command(name='delete', description='Delete a channel')
    # @app_commands.describe(channel='The channel to delete')
    # async def channel_delete(self, interaction: discord.Interaction, channel: discord.TextChannel):
    #     if not cast(discord.Member, interaction.user).guild_permissions.manage_channels:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `manage_channels` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await interaction.response.send_message(embed=discord.Embed(
    #             title='Channel deleted',
    #             description=f'{self.emoji.checkmark} `{channel.name}` has been deleted',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         ))
    #         await channel.delete()
    #     except discord.Forbidden:
    #         await interaction.response.send_message(embed=discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `manage_channels` permission or channel is above me in hierarchy',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         ))

    # @channel_group.command(name='purge', description='Purge messages from a channel')
    # @app_commands.describe(amount='Number of messages to purge', channel='The channel to purge')
    # async def channel_purge(self, interaction: discord.Interaction, amount: int, channel: discord.TextChannel = None): # pyright: ignore[reportArgumentType]
    #     if not cast(discord.Member, interaction.user).guild_permissions.manage_channels:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `manage_channels` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     target = channel or interaction.channel
    #     try:
    #         deleted = await target.purge(limit=amount) # pyright: ignore[reportAttributeAccessIssue]
    #         embed = discord.Embed(
    #             title='Channel purged',
    #             description=f'{self.emoji.checkmark} Deleted `{len(deleted)}` messages in <#{target.id}>',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `manage_messages` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed, ephemeral=True)

    # @channel_group.command(name='sync', description='Sync channel permissions with its category')
    # @app_commands.describe(channel='The channel to sync')
    # async def channel_sync(self, interaction: discord.Interaction, channel: discord.TextChannel):
    #     if not cast(discord.Member, interaction.user).guild_permissions.manage_channels:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `manage_channels` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     if not channel.category:
    #         await interaction.response.send_message(embed=discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Channel has no category to sync with',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         ), ephemeral=True)
    #         return

    #     try:
    #         await channel.edit(sync_permissions=True)
    #         embed = discord.Embed(
    #             title='Channel synced',
    #             description=f'{self.emoji.checkmark} <#{channel.id}> permissions synced with `{channel.category.name}`',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #     except discord.Forbidden:
    #         embed = discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `manage_channels` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )

    #     await interaction.response.send_message(embed=embed)

    # @channel_group.command(name='recreate', description='Recreate a channel')
    # @app_commands.describe(channel='The channel to recreate')
    # async def channel_recreate(self, interaction: discord.Interaction, channel: discord.TextChannel):
    #     if not cast(discord.Member, interaction.user).guild_permissions.manage_channels:
    #         embed = discord.Embed(
    #             title='Forbidden',
    #             description=f'{self.emoji.crossmark} You are missing `manage_channels` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return

    #     try:
    #         await interaction.response.defer()
    #         new_channel = await channel.clone()
    #         await new_channel.edit(position=channel.position, sync_permissions=True)
    #         await channel.delete()
    #         embed = discord.Embed(
    #             title='Channel recreated',
    #             description=f'{self.emoji.checkmark} <#{new_channel.id}> has been recreated',
    #             color=discord.Color.from_rgb(125, 239, 53)
    #         )
    #         await new_channel.send(embed=embed)
    #     except discord.Forbidden:
    #         await interaction.response.send_message(embed=discord.Embed(
    #             title='Failed',
    #             description=f'{self.emoji.crossmark} Missing `manage_channels` permission',
    #             color=discord.Color.from_rgb(239, 57, 57)
    #         ))
