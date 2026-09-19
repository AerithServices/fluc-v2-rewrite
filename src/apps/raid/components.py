from __future__ import annotations

__all__ = (
    'SpamMenu',
    'Nitro',
    'Giveaway'
)

import queue
import discord
import asyncio
import time
import utils
import requests.adapters
import datetime
from utils.models import User
from utils.state import State
from discord import ui
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Generator

class ChannelSpam:
    def __init__(self):
        self.queue = queue.Queue()
        self.interactions: list[discord.Interaction] = []
        self.workers = 20
        self.stopped = False
        self.sending = False
        self.executor = None

    def submit(self, view: SpamMenu):
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=self.workers)
        interactions = self.interactions.copy()
        self.interactions.clear()
        gen = view.get_followup(interactions)
        for _ in range(30):
            try:
                followup = next(gen)
            except StopIteration:
                return
            self.executor.submit(view.send_message, followup, self)
        for followup in gen:
            self.queue.put((followup, 1.5))

    def consume(self, view: SpamMenu):
        while True:
            try:
                followup, retry_after = self.queue.get(timeout=5)
            except queue.Empty:
                break
            if self.stopped:
                break
            time.sleep(retry_after)
            view.send_message(followup, self)
            self.queue.task_done()

        self.sending = False
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None

    def stop(self):
        self.interactions.clear()
        self.stopped = True
        with self.queue.mutex:
            self.queue.queue.clear()
        self.sending = False
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None


class SpamMenu(ui.View):
    interactions: list[discord.Interaction]
    views: dict[tuple[int, int], ChannelSpam] = {}

    def __init__(self, interaction: Optional[discord.Interaction] = None, user: Optional[User] = None):
        super().__init__(timeout=None)
        # Constant 30
        self.limit = 40
        self.fire_interaction: Optional[discord.Interaction] = None
        self.embed = discord.Embed(
            title='**Fluc**',
            description=(
                'Menu\n'
                '> "Fire" to start spamming.\n'
                '> "+5 messages" to add more messages.\n'
            ),
            # White
            color=discord.Color.from_str('#FFF')
        )
        user = user or User.new(State, 0)
        self.settings = user.settings
        self.embed.set_thumbnail(url='https://api.fluc.lol/assets/v2/fluc.png')
        state = type(self).get_state(interaction)
        if interaction:
            state.interactions.append(interaction)
        self.update_queue(base=interaction and 10 or 5)

    @classmethod
    def get_state(cls, interaction: Optional[discord.Interaction] = None) -> ChannelSpam:
        if interaction is None:
            return ChannelSpam()
        channel_id = interaction.channel_id
        if channel_id is None:
            channel_id = getattr(interaction.channel, 'id', None)
        if channel_id is None:
            return ChannelSpam()
        user_id = interaction.user.id
        key = (channel_id, user_id)
        state = cls.views.get(key)
        if state is None:
            state = ChannelSpam()
            cls.views[key] = state
        return state

    def update_queue(self, interaction: Optional[discord.Interaction] = None, base: int = 5, ignore_queue: bool = False):
        state = self.get_state(interaction)
        self.embed.clear_fields()
        count = base
        if not ignore_queue:
            # followups * 5 + base interaction
            count = len(state.interactions) * 5 + count
        self.embed.add_field(name='Queue', value=f'**{count}** messages will be sent.')

    def get_followup(self, interactions: list[discord.Interaction]) -> Generator[str, None, None]:
        webhook_url = 'https://discord.com/api/webhooks/{}/{}'
        for interaction in interactions[:]:
            for _ in range(5):
                followup = interaction.followup
                yield webhook_url.format(followup.id, followup.token)
            interactions.remove(interaction)

    def submit(self, state: ChannelSpam):
        state.submit(self)

    def send_message(self, webhook: str, state: ChannelSpam):
        session = requests.Session()
        # Make session be able to handle state.workers concurrent requests
        adapter = requests.adapters.HTTPAdapter(pool_connections=state.workers, pool_maxsize=state.workers)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        # embed= discord.Embed(
        #     title='Raid by Fluc',
        #     description='Join https://discord.gg/fluc today'
        # )
        # embed.set_thumbnail(url='https://api.fluc.lol/assets/icons/nuke_glitch.gif')
        # data = {
        #     'content': '# RAID BY discord.gg/fluc\n-# @everyone @here',
        #     'tts': True,
        #     'embeds': [embed.to_dict()],
        #     'allowed_mentions': {
        #         'parse': [
        #             'everyone',
        #             'users',
        #             'roles'
        #         ]
        #     }
        # }
        data = {
            'content': self.settings.rbot_message,
            'tts': self.settings.rbot_tts,
            'allowed_mentions': {
                'parse': [
                    'everyone',
                    'users',
                    'roles'
                ]
            }
        }
        if state.stopped:
            return
        response = session.post(webhook, json=data)
        if response.status_code == 429:
            json_data = response.json()
            retry_after = json_data.get('retry_after')
            state.queue.put((webhook, float(retry_after)))
            return
        if 200 <= response.status_code < 300:
            try:
                json_data = response.json()
            except ValueError:
                return
            flags = json_data.get('flags')
            if isinstance(flags, int) and flags & 0x40:
                # Message was sent as ephemeral - external app perms disabled
                state.stop()
                return
        if response.status_code == 403:
            try:
                json_data = response.json()
                error_message = json_data.get('message', '')
            except ValueError:
                error_message = response.text
            if 'external app' in error_message.lower() or 'disallowed' in error_message.lower() or 'cannot send messages' in error_message.lower():
                state.stop()
                return

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def disable(self, interaction: discord.Interaction):
        self.button_add.disabled = True
        self.button_fire.disabled = True
        self.button_stop.disabled = True
        await self.update(interaction)

    @ui.button(label='+5 messages', custom_id='plus_5_messages')
    async def button_add(self, interaction: discord.Interaction, _):
        if not utils.can_flood(interaction):
            await interaction.response.send_message('This channel cannot be flooded.')
            return
        state = type(self).get_state(interaction)
        state.interactions.append(interaction)
        self.update_queue(interaction)
        if len(state.interactions) >= self.limit // 5 - 1:
            self.button_add.disabled = True
        await self.update(interaction)

    @ui.button(label='🔥FIRE', custom_id='fire')
    async def button_fire(self, interaction: discord.Interaction, _):
        self.button_add.disabled = False
        state = type(self).get_state(interaction)
        state.stopped = False
        state.interactions.append(interaction)
        self.fire_interaction = interaction
        self.update_queue(ignore_queue=True)
        asyncio.create_task(self.update(interaction))

        if state.sending and state.executor:
            self.submit(state)
            return

        state.sending = True
        self.submit(state)
        assert state.executor is not None
        state.executor.submit(state.consume, self)

    @ui.button(label='🛑Stop', custom_id='button_stop')
    async def button_stop(self, interaction: discord.Interaction, _):
        state = type(self).get_state(interaction)
        await interaction.response.defer(ephemeral=True)
        state.stop()


class Nitro(ui.LayoutView):
    def __init__(self, count: int = 0, user: Optional[User] = None):
        super().__init__(timeout=None)
        u_2800 = chr(0x2800)
        expires = utils.now(hours=2)
        self.user = user
        self.count = count
        self.button = ui.Button(
            label='Open Gift',
            custom_id='accept',
            style=discord.ButtonStyle.primary
        )
        self.button.callback = self.button_callback
        self.expires = int(expires.timestamp())
        self.content = (
            '## You\'ve been gifted a subscription!\n'
            '**fluc** has gifted you Nitro for **1 month**' + u_2800 * 13 +
            '\n\n\n\n' +
            u_2800 * 19 + f'Expires <t:{self.expires}:R>'
        )
        self.container = ui.Container(
            ui.Section(
                ui.TextDisplay(self.content),
                accessory=ui.Thumbnail('https://api.fluc.lol/assets/icons/nitro_gift.png'),
            ),
            ui.ActionRow(self.button)
        )
        self.add_item(self.container)
    
    async def button_callback(self, interaction: discord.Interaction):
        if self.count > 4:
            self.button.disabled = True
            await interaction.response.edit_message(view=self)
        self.count += 1
        await utils.raid(interaction, self.user, ephemeral=False)

class Giveaway(ui.View):
    def __init__(self, count: int = 0, user: Optional[User] = None, title: Optional[str] = None, hosted_by: Optional[str] = None, expires: datetime.datetime = utils.now(days=2)):
        super().__init__(timeout=None)
        title = title or '10$ Nitro Giveaway'
        hosted_by = hosted_by or 'Fluc'
        description = (
            f'Ends: <t:{int(expires.timestamp())}:R>\n'
            f'Hosted by: **{hosted_by}**\n'
            'Entries **6**\n'
            'Winners: **2**'
        )
        self.user = user
        self.count = count
        self.button = ui.Button(
            label='🎉 Join',
            custom_id='join',
            style=discord.ButtonStyle.primary
        )
        self.button.callback = self.button_callback
        self.expires = int(expires.timestamp())
        self.embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple(),
            timestamp=utils.now()
        )
        self.add_item(self.button)
    
    async def button_callback(self, interaction: discord.Interaction):
        if self.count > 4:
            self.button.disabled = True
            await interaction.response.edit_message(view=self)
        self.count += 1
        await utils.raid(interaction, self.user, ephemeral=False)

