import os
import asyncio
import discord
import aiohttp
import utils
from utils import runner
from utils.state import State
from utils.modified import ConnectedBot
from utils.http_utils import make_socket_factory
from app_types import BotConfig
from discord.ext import commands
from .commands import Commands
from .events import Events
from .components import SpamMenu, Nitro, Giveaway

async def setup(bot: ConnectedBot):
    await bot.add_cog(Events(bot))
    await bot.add_cog(Commands(bot))
    bot.add_view(Nitro(5))
    bot.add_view(Giveaway(5))
    bot.add_view(SpamMenu())
    

async def mainloop():
    with open('config/bot.json') as file:
        bot_config = BotConfig.model_validate_json(file.read())
    connector = aiohttp.TCPConnector(
        socket_factory=make_socket_factory(bot_config.http.raid)
    )
    bot = commands.Bot(
        command_prefix=State.command_prefixes,
        intents=discord.Intents.default(),
        help_command=None,
        connector=connector
    )
    setattr(type(bot), 'session', property(utils.get_session))
    await bot.login(os.getenv('RAID_TOKEN', ''))
    if not await utils.api_status(bot, ignore_webhook=True): # pyright: ignore[reportArgumentType]
        return True
    await setup(bot) # pyright: ignore[reportArgumentType]
    try:
        async with bot:
            await bot.connect()
        return True
    except asyncio.CancelledError:
        return True

asyncio.run(runner(mainloop))
