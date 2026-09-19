__all__ = (
    'BotInvite',
    'TicketView'
)

import os
import discord
import utils
import aiohttp
from discord import ui
from typing import Optional

class URLButton(ui.View):
    def __init__(self, label: str, url: str):
        super().__init__(timeout=None)
        button = ui.Button(
            label=label,
            url=url
        )
        self.add_item(button)


class BotInvite(ui.View):
    def __init__(self, author_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.disabled = author_id is None
        # White
        white = discord.Color.from_str('#FFF')
        self.embed = discord.Embed(
            title='Bot Invite',
            description=(
                'Click the button below to get the bot.\n'
                f'> Note: If the button does not work, you can get the bot at https://fluc.lol/get-bot\n'
                '-# Info about how we handle your data can be found at https://fluc.lol/pp'
            ),
            color=white
        )
        # We don't want to make this a url button,
        # because that wouldn't let us change it later
        button = ui.Button(
            label='🤖 Get Bot',
            custom_id='get_bot',
            disabled=self.disabled
        )
        button.callback = self.button_callback 
        self.button = button
        self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        if self.disabled:
            await interaction.response.edit_message(embed=self.embed, view=self)
            await interaction.followup.send('This button has expired.', ephemeral=True)
            return
        if not interaction.user.id == self.author_id:
            await interaction.response.send_message('Please run .invite to get the bot.', ephemeral=True)
            return
        self.disabled = True
        self.button.disabled = True
        if interaction.message:
            await interaction.message.edit(embed=self.embed, view=self)
        async with aiohttp.ClientSession() as session:
            session.headers['authorization'] = os.getenv('UTILITY_TOKEN', '')
            async with session.get('https://api.fluc.lol/verify/get-url?get_bot=true') as response:
                if not response.ok:
                    await interaction.response.send_message('Seems like Fluc API is down. Please try again later.', ephemeral=True)
                    return
                data = await response.json()
                url = data['url']
        view = URLButton('Authorize', url)
        await interaction.response.send_message(
            f'After authorizing, close the page and check your servers.',
            view=view,
            ephemeral=True
        )


class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        button = ui.Button(
            label='Create ticket',
            custom_id='ticket'
        )
        button.callback = self.button_callback
        self.embed = discord.Embed(
            title='Support Ticket',
            description='After opening ticket, please state your issue.',
            color=discord.Color.from_str('#FFF')
        )
        self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        assert guild
        category = discord.utils.get(guild.channels, name='?')
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                'Ticket category not found. Please let staff know about this issue.',
                ephemeral=True
            )
            return
        name = utils.strip_special(interaction.user.name)
        open_tickets: list[discord.TextChannel] = []
        for channel in category.channels:
            if channel.name.startswith(name):
                if not channel.type is discord.ChannelType.text:
                    continue
                open_tickets.append(channel)
        
        if len(open_tickets) >= 1:
            await interaction.response.send_message(
                'You have reached the limit of 1 tickets.',
                ephemeral=True
            )
            return
        
        member = guild.get_member(interaction.user.id)
        assert member
        taken_nums = []
        for ticket in open_tickets:
            last_char = ticket.name[-1]
            if last_char.isdigit():
                taken_nums.append(int(last_char))

        taken_nums.sort()
        free_num = 1

        for num in taken_nums:
            if free_num == num:
                free_num += 1
            elif num > free_num:
                break

        channel_name = name + f'-{free_num}'
        last_position = max(
            (ch.position for ch in open_tickets),
            default=0
        )
        
        overwrites = category.overwrites
        overwrites.update({
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
        })
        ticket = await category.create_text_channel(
            channel_name,
            overwrites=overwrites,
            position=last_position
        )
        await interaction.response.send_message(
            f'Ticket created at {ticket.mention}',
            ephemeral=True
        )
        readmes = [
            'https://nohello.net/en/',
            'https://dontasktoask.com/',
            'http://catb.org/~esr/faqs/smart-questions.html'
        ]
        await ticket.send(f'@everyone {interaction.user.mention} created a new ticket\n' + '\n'.join(readmes))
