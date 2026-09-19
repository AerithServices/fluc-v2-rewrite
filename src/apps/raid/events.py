import logging
import utils
import traceback
from discord.ext import commands
from discord.ext.tasks import loop as task_loop
from utils.modified import ConnectedBot, EventCog
from utils.state import State

log = logging.getLogger('fluc')

class Events(EventCog):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot

    @task_loop(seconds=30)
    async def api_status(self):
        await utils.api_status(self.bot, ignore_webhook=True)

    @commands.Cog.listener()
    async def on_ready(self):
        State.is_ready = True
        self.api_status.start()
        log.info(f'Connected as {self.bot.user} (ID: {self.bot.user.id})')
        await self.bot.tree.sync()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exc: Exception, *args):
        if isinstance(exc, commands.CheckFailure):
            return
        log.error(traceback.format_exc())
        
    async def cog_unload(self):
        if self.api_status.is_running():
            self.api_status.cancel()
