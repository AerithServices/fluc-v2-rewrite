import discord
from discord import app_commands
from discord.ext import commands
from utils.modified import ConnectedBot, GuildInteraction
from utils.commands import command_hook, Cooldown, CooldownCheck as CdCheck, CommandFlags
from utils.enums import CooldownType as CdType
from utils.state import State
from utils.models import UserFlags
from typing import Optional, cast


class Stats(commands.Cog):
    def __init__(self, bot: ConnectedBot) -> None:
        self.bot = bot

    async def fetch_rank(self, user_id: int) -> Optional[int]:
        # I know this is super messy. Basically what we're doing is
        # getting user's position on the leaderboard
        user_data = await State.db.query(
            '''
            SELECT * FROM (
                SELECT user_id, COUNT(*) AS member_count,
                    ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, user_id = %s DESC) AS user_rank
                FROM stats GROUP BY user_id
            ) AS leaderboard
            WHERE user_id = %s;
            ''',
            (user_id, user_id),
            fetchall=False
        )
        if user_data:
            return user_data['user_rank']

    @app_commands.command()
    @app_commands.describe(user='User to lookup.')
    @command_hook(
        Cooldown(CdCheck(CdType.USER, 1, 3)),
        flags=CommandFlags(bypass_protected=True, bypass_whitelist=True),
    )
    async def stats(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        '''Show nake stats for a specific user.'''
        interaction = cast(GuildInteraction, interaction)
        user_id = interaction.user.id
        if user:
            user_id = user.id
        user_ = await State.db.get_user(user_id, with_stats=True)
        if not user_:
            await interaction.response.send_message('User not found.', ephemeral=True)
            return
        assert user_.stats
        if user_id != interaction.user.id:
            if user_.is_private:
                await interaction.response.send_message('This profile is private.', ephemeral=True)
                return
        member = interaction.guild.get_member(user_id) or f'<@{user_id}>'
        embed = discord.Embed(
            title=member,
            description=f'Nake stats for {member}#{user_id}'
        )
        servers_naked = len(user_.stats.servers)
        members_naked = len(user_.stats.members)
        rank = '#'
        rank += str(await self.fetch_rank(user_.id)) or '??'
        embed.add_field(
            name='Members naked',
            value=f'`{members_naked}`'
        )
        embed.add_field(
            name='Servers naked',
            value=f'`{servers_naked}`'
        )
        embed.add_field(
            name='Rank',
            value=f'`{rank}`'
        )
        if not isinstance(member, str):
            if member.avatar:
                url = member.avatar.url
            else:
                url = member.default_avatar.url
            embed.set_thumbnail(url=url)
        await interaction.response.send_message(embed=embed, ephemeral=user_.is_private)

    @app_commands.command()
    @command_hook(
        Cooldown(CdCheck(CdType.USER, 1, 3)),
        flags=CommandFlags(bypass_protected=True, bypass_whitelist=True),
    )
    async def gstats(self, interaction: discord.Interaction):
        '''Shows global nake stats.'''
        members = await State.db.query(
            'SELECT COUNT(DISTINCT member_id) FROM stats;',
            fetchall=False
        )
        servers = await State.db.query(
            'SELECT COUNT(DISTINCT server_id) FROM stats;',
            fetchall=False
        )
        users = await State.db.query(
            'SELECT COUNT(DISTINCT user_id) FROM users;',
            fetchall=False
        )
        assert members
        assert servers
        assert users
        embed = discord.Embed(
            title='Global Stats',
            color=discord.Color.blurple()
        )
        embed.add_field(
            name='Members naked',
            value=f'`{list(members.values())[0]}`'
        )
        embed.add_field(
            name='Servers naked',
            value=f'`{list(servers.values())[0]}`'
        )
        embed.add_field(
            name='Users',
            value=f'`{list(users.values())[0]}`'
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @command_hook(
        Cooldown(CdCheck(CdType.USER, 1, 3)),
        flags=CommandFlags(bypass_protected=True, bypass_whitelist=True),
    )
    async def leaderboard(self, interaction: discord.Interaction):
        '''Shows top 10 users with most naked members.'''
        interaction = cast(GuildInteraction, interaction)
        members_raw = await State.db.query(
            '''
            SELECT user_id, COUNT(*) AS member_count FROM stats
            GROUP BY user_id ORDER BY member_count DESC
            LIMIT 10;
            '''
        )
        user_ids = []
        users = {}
        for stats in members_raw:
            user_ids.append(stats['user_id'])

        placeholders = ','.join(['%s'] * len(user_ids))
        servers_raw = await State.db.query(
            f'''
            SELECT user_id, COUNT(DISTINCT server_id) AS server_count
            FROM stats WHERE user_id IN ({placeholders})
            GROUP BY user_id ORDER BY server_count DESC
            LIMIT 10;
            ''',
            user_ids
        )
        server_data = {
            item['user_id']: item['server_count']
            for item in servers_raw
        }
        member_data = {
            item['user_id']: item['member_count']
            for item in members_raw
        }
        raw_users = await State.db.query(
            f'SELECT * FROM users WHERE user_id IN ({placeholders})',
            user_ids
        )
        user_lookup = {user['user_id']: user for user in raw_users}

        if not interaction.user.id in user_ids:
            user_rank = await self.fetch_rank(interaction.user.id) or '??'
        else:
            user_rank = None
        for rank, stats in enumerate(members_raw, 1):
            user = user_lookup[stats["user_id"]]
            # This basically reverses the list
            member = interaction.guild.get_member(user['user_id'])
            flags = UserFlags(user['flags'])
            data = {
                'name': member.name if member else user['user_id'],
                'members': member_data[user['user_id']],
                'servers': server_data[user['user_id']],
                'rank': rank
            }
            if flags.is_private and not flags.is_super:
                data['name'] = 'Private Profile'
            users[user['user_id']] = data

        fields = []
        values = list(users.values())
        for i, user in enumerate(values, 1):
            name = f'{i}. {user['name']}'
            inline = True
            match i:
                case 1:
                    name = name.replace('1.', ':medal:')
                case 2:
                    name = name.replace('2.', ':second_place:')
                case 3:
                    name = name.replace('3.', ':third_place:')
                case _:
                    inline = False
            value = f'> Members: **{user['members']}**\n'
            value += f'> Servers: **{user['servers']}**'
            fields.append((name, value, inline))

        if not user_rank:
            user_rank = users[interaction.user.id]['rank']

        embed = discord.Embed(
            title='Fluc Leaderboard',
            # White
            color=discord.Color.from_str('#fff')
        )
        embed.set_thumbnail(url='https://api.fluc.lol/assets/v2/fluc.png')
        for field in fields:
            embed.add_field(name=field[0], value=field[1], inline=field[2])
        embed.set_footer(text=f'Your position on the leaderboard is #{user_rank}')
        await interaction.response.send_message(embed=embed)
