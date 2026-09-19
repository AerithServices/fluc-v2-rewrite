import discord
import utils
import io
import numpy as np
from discord import app_commands
from discord.ext import commands
from utils.commands import command_hook
from utils.enums import Permissions
from typing import Literal

class FunCommands(commands.GroupCog, name='fun'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(
        expression='Bytebeat expression',
        sample_rate='Frequency',
        duration='Duration in seconds',
        dtype='Datatype of bytebeat'
    )
    @command_hook(permissions=Permissions.ELEVATED)
    async def bytebeat(
        self,
        interaction: discord.Interaction,
        expression: str = 't >> 1',
        sample_rate: app_commands.Range[int, 1, 100000] = 8000,
        duration: app_commands.Range[int, 1, 60] = 30,
        dtype: Literal['int8', 'uint8', 'int16', 'uint16', 'float'] = 'uint8'
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        type_ = np.uint8
        match dtype:
            case 'int8':
                type_ = np.int8
            case 'uint8':
                type_ = np.uint8
            case 'int16':
                type_ = np.int16
            case 'uint16':
                type_ = np.uint16
            case 'float':
                type_ = np.float32
        samples = await utils.render_bytebeat(
            expression,
            sample_rate,
            duration,
            type_
        )
        buff = io.BytesIO()
        utils.save_wav(buff, samples, sample_rate)
        buff.seek(0)
        file = discord.File(buff, filename='output.wav')
        await interaction.channel.send(file=file)