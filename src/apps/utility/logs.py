import logging
import discord
import utils
import utils
import os
from discord.ext import commands
from utils.modified import ConnectedBot, EventCog

log = logging.getLogger('fluc')

class MemberLogs(EventCog):
    def __init__(self, bot: ConnectedBot) -> None:
        webhook = 'https://discord.com/api/webhooks/{}/{}'
        webhook = webhook.format(os.getenv('LOG_WEBHOOK_ID', ''), os.getenv('LOG_WEBHOOK_TOKEN', ''))
        self.log = discord.Webhook.from_url(webhook, session=bot.session)
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        deleted_by = None
        if not message.guild or not message.channel:
            return
        async for audit in message.guild.audit_logs(limit=1):
            if audit.action is discord.AuditLogAction.message_delete:
                if audit.target == message.author:
                    if audit.created_at >= utils.now(seconds=2, reverse=True):
                        deleted_by = audit.user
                        break
        else:
            deleted_by = message.author
        if deleted_by == message.guild.me:
            return
        description = (
            f'Author: {message.author.mention}#{message.author}\n'
            f'Sent at: <t:{int(message.created_at.timestamp())}:R>\n'
            f'Channel: <#{message.channel.id}>#{getattr(message.channel, 'name', None)}\n'
        )
        if deleted_by:
            description += f'Deleted by: {deleted_by.mention}#{deleted_by}'
        embed = discord.Embed(
            title='Deleted message',
            description=description,
            color=discord.Color.red()
        )
        embed.add_field(
            name='Content',
            value=message.content[:2000]
        )
        await self.log.send(embed=embed)