import discord
import aiohttp
import asyncio
import logging
import utils
import os

from utils import runner
from utils.modified import ConnectedBot
from utils.state import State
from utils.http_utils import make_socket_factory
from discord.ext import commands
from app_types import BotConfig
from .commands import Commands
from .events import Events

try:
    import uvloop # pyright: ignore[reportMissingImports]
    new_event_loop = uvloop.new_event_loop
except ImportError:
    new_event_loop = None

log = logging.getLogger('fluc')

async def setup(bot: ConnectedBot):
    await bot.add_cog(Commands(bot))
    await bot.add_cog(Events(bot))

async def mainloop() -> bool:
    with open('config/bot.json') as file:
        bot_config = BotConfig.model_validate_json(file.read())
    log.debug('Created new connector.')
    connector = aiohttp.TCPConnector(
        # Decrease limits
        limit=0,
        limit_per_host=0,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
        force_close=False,
        keepalive_timeout=30,
        # Skip SSL checks that may cause additional trouble
        ssl=False,
        socket_factory=make_socket_factory(bot_config.http.nuke)
    )
    State.load_fonts('fonts.txt', 'fonts2.txt')
    State.load_phrases('fluc', 'phrases.txt')
    with open('data/avatars.txt') as file:
        content = file.read()
    avatars = content.strip().splitlines()
    State.avatars.extend(avatars)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    log.debug('Created new bot.')
    bot = commands.Bot(
        command_prefix=State.command_prefixes,
        intents=intents,
        case_insensitive=True,
        strip_after_prefix=True,
        # Remove default help command
        help_command=None,
        connector=connector
    )
    setattr(type(bot), 'session', property(utils.get_session))
    try:
        log.debug('Logging in.')
        await bot.login(os.getenv('NUKE_TOKEN', ''))
    except (discord.LoginFailure, discord.HTTPException, aiohttp.ClientConnectionError) as exc:
        log.error(exc)
        if 'temporary banned' in str(exc):
            log.info('Attempting to reconnect using different IPV4.')
            return True
        if 'Improper token' in str(exc):
            return False
        if isinstance(exc, aiohttp.ClientConnectionError):
            if 'The requested address is not valid in its context' in str(exc):
                log.warning('Make sure you have access to all the IPv4 addresses provided in config.')
                return True
        if isinstance(exc, aiohttp.ClientConnectorDNSError):
            log.warning('Are you connected to the internet?')
        return False
    finally:
        if not bot.user:
            # Bot failed to login - close season
            await bot.close()
    # Check API status immediately after connecting
    if not await utils.api_status(bot): # pyright: ignore[reportArgumentType]
        return True
    # bot is now ConnectedBot
    # Will break bot - just suppress error
    # bot = ConnectedBot(bot)
    await setup(bot) # pyright: ignore[reportArgumentType]
    log.debug('Bot is ready to connect.')
    try:
        async with bot:
            log.debug('Connecting.')
            # Check comment in utils.api_status
            await bot.connect(reconnect=False)
        # Unexpected .close()? Reconnect
        return True
    except (discord.PrivilegedIntentsRequired, aiohttp.ClientConnectorDNSError, discord.ConnectionClosed) as exc:
        log.error(exc)
        if isinstance(exc, aiohttp.ClientConnectorDNSError):
            # Attempt to reconnect on different IPv4 (will most likely fail)
            return True
        if isinstance(exc, discord.ConnectionClosed):
            # Most likely token reset/bot deleted.
            # Retry and we'll see what's going on
            return True
    except asyncio.CancelledError:
        return True
    return False
    
asyncio.run(runner(mainloop), loop_factory=new_event_loop)
