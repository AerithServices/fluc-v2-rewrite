import discord
import logging
from discord import app_commands
from utils.commands import command_hook, Permissions
from discord.ext import commands
from utils.modified import ConnectedBot
from typing import Optional
from ..components import TicketView

log = logging.getLogger('fluc')

class TicketCommands(commands.GroupCog, name='ticket'):
    def __init__(self, bot: ConnectedBot):
        self.bot = bot

    @app_commands.command()
    @command_hook(permissions=Permissions.PUBLIC)
    async def open(self, intreaction: discord.Interaction):
        '''Opens a ticket.'''
        view = TicketView()
        await intreaction.response.send_message(
            embed=view.embed,
            view=view
        )

    @app_commands.command()
    @app_commands.describe(reason='Reason for this action.')
    @command_hook(permissions=Permissions.PUBLIC)
    async def close(self, interaction: discord.Interaction, reason: Optional[str] = 'No reason specified.'):
        '''Closes a ticket channel.'''
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        category = interaction.channel.category
        if not category or not category.name == '?':
            await interaction.response.send_message('This channel is not a ticket.', ephemeral=True)
            return
        if not interaction.channel.overwrites or interaction.channel.name.startswith('closed-'):
            await interaction.response.send_message('This ticket is closed.', ephemeral=True)
            return
        await interaction.channel.edit(
            name=f'closed-' + interaction.channel.name,
            overwrites=category.overwrites
        )
        await interaction.response.send_message(
            f'Ticket closed by {interaction.user}#{interaction.user.id} with reason:\n{reason}'
        )

    @app_commands.command()
    @app_commands.describe(reason='Reason for this action.')
    @command_hook(permissions=Permissions.MOD)
    async def delete(self, interaction: discord.Interaction, reason: Optional[str] = 'No reason was provided.'):
        '''Deletes a ticket.'''
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        category = interaction.channel.category
        if not category or not category.name == '?':
            await interaction.response.send_message('This channel is not a ticket.', ephemeral=True)
            return
        await interaction.channel.delete(reason=reason)

    @app_commands.command()
    @app_commands.describe(new_name='New name for ticket', reason='Reason for this action.')
    @command_hook(permissions=Permissions.MOD)
    async def rename(self, interaction: discord.Interaction, new_name: str, reason: Optional[str] = 'No reason was provided.'):
        '''Renames ticket.'''
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        category = interaction.channel.category
        if not category or not category.name == '?':
            await interaction.response.send_message('This channel is not a ticket.', ephemeral=True)
            return
        name = interaction.channel.name
        has_name = len(name.split('-')) == 3
        if has_name:
            keep = name.split('-')[1:]
        else:
            keep = name.split('-')
        name = new_name + '-' + '-'.join(keep)
        await interaction.channel.edit(name=name, reason=reason)
        await interaction.response.send_message('Renamed ticket.')

    @app_commands.command()
    @app_commands.describe(member='Member to add to ticket.', reason='Reason for this action.')
    @command_hook(permissions=Permissions.MOD)
    async def add(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = 'No reason was provided.'):
        '''Adds user to ticket.'''
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        category = interaction.channel.category
        if not category or not category.name == '?':
            await interaction.response.send_message('This channel is not a ticket.', ephemeral=True)
            return
        overwrites = interaction.channel.overwrites
        overwrites[member] = discord.PermissionOverwrite(view_channel=True)
        await interaction.channel.edit(overwrites=overwrites, reason=reason)
        await interaction.response.send_message(f'Added {member.mention} to {interaction.channel.mention}.')

    @app_commands.command()
    @app_commands.describe(member='Member to remove from ticket.', reason='Reason for this action.')
    @command_hook(permissions=Permissions.MOD)
    async def remove(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = 'No reason was provided.'):
        '''Removes user from ticket.'''
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        category = interaction.channel.category
        if not category or not category.name == '?':
            await interaction.response.send_message('This channel is not a ticket.', ephemeral=True)
            return
        overwrites = interaction.channel.overwrites
        overwrites.pop(member)
        await interaction.channel.edit(overwrites=overwrites, reason=reason)
        await interaction.response.send_message(f'Removed {member.mention} from {interaction.channel.mention}.')