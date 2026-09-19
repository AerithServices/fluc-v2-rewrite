import os
import asyncio
import discord
import utils
import aiohttp
from logging import getLogger
from utils import runner
from utils.http_utils import make_socket_factory
from utils.state import State
from utils.modified import ConnectedBot
from app_types import BotConfig
from discord.ext import commands
from .commands.commands import Commands
from .commands.db import DatabaseCommands
from .commands.ticket import TicketCommands
from .commands.mod import ModCommands
from .commands.fun import FunCommands
from .commands.customize import Customize
from .commands.stats import Stats
from .commands.fuck import FuckCommands
from .events import Events
from .logs import MemberLogs
from .components import BotInvite, TicketView

log = getLogger('fluc')

async def setup(bot: ConnectedBot):
    await bot.add_cog(Events(bot))
    await bot.add_cog(Commands(bot))
    await bot.add_cog(DatabaseCommands(bot))
    await bot.add_cog(TicketCommands(bot))
    await bot.add_cog(ModCommands(bot))
    await bot.add_cog(FunCommands(bot))
    await bot.add_cog(Customize(bot))
    await bot.add_cog(Stats(bot))
    await bot.add_cog(FuckCommands(bot))
    await bot.add_cog(MemberLogs(bot))
    bot.add_view(BotInvite())
    bot.add_view(TicketView())

async def mainloop():
    if os.getenv('DEV'):
        log.error('Cannot run utility in DEV mode.')
        return
    with open('config/bot.json') as file:
        bot_config = BotConfig.model_validate_json(file.read())
    connector = aiohttp.TCPConnector(
        socket_factory=make_socket_factory(bot_config.http.utility)
    )
    bot = commands.Bot(
        command_prefix=State.command_prefixes,
        intents=discord.Intents.all(),
        help_command=None,
        connector=connector,
        case_insensitive=True,
        strip_after_prefix=True
    )
    State.load_tlds('tlds.txt')
    setattr(type(bot), 'session', property(utils.get_session))
    await bot.login(os.getenv('UTILITY_TOKEN', ''))
    if not await utils.api_status(bot, ignore_webhook=True): # pyright: ignore[reportArgumentType]
        return True
    await setup(bot) # pyright: ignore[reportArgumentType]
    try:
        async with bot:
            await bot.connect()
    except asyncio.CancelledError:
        return True

asyncio.run(runner(mainloop))
