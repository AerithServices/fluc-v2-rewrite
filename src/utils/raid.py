__all__ = (
    'raid',
    'can_flood'
)

import requests
import asyncio
import discord
from concurrent.futures import ThreadPoolExecutor
from utils.models import User
from utils.state import State
from typing import Optional

async def raid(interaction: discord.Interaction, user: Optional[User] = None, ephemeral: bool = True, delay_override: int = 0):
    if not can_flood(interaction):
        await interaction.response.send_message('This channel cannot be flooded.', ephemeral=True)
        return
    allowed_mentions = discord.AllowedMentions(
        everyone=True,
        users=True,
        roles=True
    )
    
    async def meta_async():
        await interaction.response.send_message('**FOR 2X FASTER RAID AND LESS COOLDOWNS GET PREMIUM INFO IN** discord.gg/fluc', tts=True, ephemeral=True)
        for _ in range(5):
            asyncio.create_task(interaction.followup.send(
                content,
                tts=tts,
                allowed_mentions=allowed_mentions
            ))
            if delay_override:
                await asyncio.sleep(delay_override)

    async def meta_sync():
        def send():
            requests.post(interaction.followup.url, json=data)

        data = {
            'content': content,
            'tts': True,
            'allowed_mentions': {
                'parse': [
                    'everyone',
                    'users',
                    'roles'
                ]
            }
        }
        await interaction.response.send_message(
            content,
            tts=True,
            ephemeral=ephemeral,
            allowed_mentions=allowed_mentions
        )
        with ThreadPoolExecutor() as executor:
            for _ in range(5):
                executor.submit(send)
                if delay_override:
                    await asyncio.sleep(delay_override)

    user = user or User.new(State, 0)
    content = user.settings.rbot_message
    tts = user.settings.rbot_tts
    if user.is_premium:
        asyncio.run_coroutine_threadsafe(meta_sync(), asyncio.get_running_loop())
    else:
        # Async method slower
        await meta_async()

def can_flood(interaction: discord.Interaction) -> bool:
    '''
    Whether interaction channel can be flooded.

    Parameters
    ----------
    interaction : :class:`discord.Interaction`
        Interaction info.

    Returns
    -------
    bool
        Whether the channel can be flooded.
    '''
    if isinstance(interaction.channel, discord.abc.GuildChannel):
        return interaction.permissions.use_external_apps
    # Can always be used outside servers
    return True