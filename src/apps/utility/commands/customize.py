import discord
import utils
from discord import app_commands
from discord.ext import commands
from utils.state import State
from utils.models import User
from utils.commands import command_hook, Cooldown, CooldownCheck as CdCheck, CommandFlags
from utils.enums import CooldownType as CdType, Permissions
from utils.modified import ConnectedBot
from typing import Optional, Any, Union

class Customize(commands.GroupCog, name='customize'):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot
        self.interactions: dict[int, User] = {}

    def parse(self, value: Optional[Union[str, bool]]) -> Any:
        if isinstance(value, bool):
            return value
        if value and utils.is_none(value):
            return None
        return value or utils.MISSING

    @app_commands.command(description='Customize nake message.')
    @app_commands.describe(message='Message to send when naking.')
    @command_hook(cooldown=Cooldown(CdCheck(CdType.USER, 1, 3)), permissions=Permissions.PREMIUM)
    async def message(self, interaction: discord.Interaction, message: Optional[app_commands.Range[str, 0, 1800]] = None):
        user = self.interactions.pop(interaction.id)
        user.settings.update(message_content=self.parse(message))
        await State.db.set_settings(user.id, user.settings)
        await interaction.response.send_message('Settings updated.', ephemeral=True)

    @app_commands.command(description='Customize server.')
    @app_commands.describe(name='New server name when messing server.')
    @command_hook(cooldown=Cooldown(CdCheck(CdType.USER, 1, 3)), permissions=Permissions.PREMIUM)
    async def server(self, interaction: discord.Interaction, name: Optional[app_commands.Range[str, 0, 120]] = None):
        user = self.interactions.pop(interaction.id)
        user.settings.update(server_name=self.parse(name))
        await State.db.set_settings(user.id, user.settings)
        await interaction.response.send_message('Settings updated.', ephemeral=True)

    @app_commands.command(description='Customize channels.')
    @app_commands.describe(name='New channel name when creating channels.')
    @command_hook(cooldown=Cooldown(CdCheck(CdType.USER, 1, 3)), permissions=Permissions.PREMIUM)
    async def channel(self, interaction: discord.Interaction, name: Optional[app_commands.Range[str, 0, 32]] = None):
        user = self.interactions.pop(interaction.id)
        user.settings.update(channel_name=self.parse(name))
        await State.db.set_settings(user.id, user.settings)
        await interaction.response.send_message('Settings updated.', ephemeral=True)

    @app_commands.command(description='Customize r-bot.')
    @app_commands.describe(message='Message to send.', tts='Toggle text-to-speech messages.')
    @command_hook(cooldown=Cooldown(CdCheck(CdType.USER, 1, 3)), permissions=Permissions.PREMIUM)
    async def rbot(
        self,
        interaction: discord.Interaction,
        message: Optional[app_commands.Range[str, 0, 1800]] = None,
        tts: Optional[bool] = None
    ):
        user = self.interactions.pop(interaction.id)
        user.settings.update(rbot_message=self.parse(message), rbot_tts=self.parse(tts))
        await State.db.set_settings(user.id, user.settings)
        await interaction.response.send_message('Settings updated.', ephemeral=True)

    @app_commands.command(name='bot_profile', description='Customize bot profile.')
    @app_commands.describe(nick='Bot nickname.', bio='Bot bio.', avatar='Bot avatar.', banner='Bot banner.')
    @command_hook(cooldown=Cooldown(CdCheck(CdType.USER, 1, 3)), permissions=Permissions.PREMIUM)
    async def _bot_profile(
        self,
        interaction: discord.Interaction,
        nick: Optional[app_commands.Range[str, 0, 32]] = None,
        bio: Optional[app_commands.Range[str, 0, 100]] = None,
        avatar: Optional[app_commands.Range[str, 0, 120]] = None,
        banner: Optional[app_commands.Range[str, 0, 120]] = None,
    ):
        '''Updates bot profile when added to server.'''
        user = self.interactions.pop(interaction.id)
        user.settings.update(
            bot_nick=self.parse(nick),
            bot_bio=self.parse(bio),
            bot_avatar=self.parse(avatar),
            bot_banner=self.parse(banner)
        )
        await State.db.set_settings(user.id, user.settings)
        await interaction.response.send_message('Settings updated.', ephemeral=True)

    @app_commands.command(description='Updates user profile.')
    @app_commands.describe(
        private='Whether the public should be private.',
        no_data_collection='Whether to not collect data.'
    )
    @command_hook(cooldown=Cooldown(CdCheck(CdType.USER, 1, 3)))
    async def profile(
        self,
        interaction: discord.Interaction,
        private: Optional[bool] = None,
        no_data_collection: Optional[bool] = None
    ):
        user = self.interactions.pop(interaction.id)
        if private is not None:
            user.flags.is_private = private
        if no_data_collection is not None:
            user.flags.no_data_collection = no_data_collection
        await State.db.set_user(user)
        await interaction.response.send_message('Profile updated.', ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        user = await State.db.get_user(interaction.user.id)
        # TODO: Auto cleanup
        # User can be None but these commands can be used only by users
        # so this is not an issue
        self.interactions[interaction.id] = user # pyright: ignore[reportArgumentType]
        return True
