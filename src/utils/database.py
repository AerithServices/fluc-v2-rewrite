from __future__ import annotations
__all__ = (
    'Database',
)

import aiomysql
import asyncio
import aiohttp
import orjson
import logging
import errno
import utils
import os
import functools
import uuid

from itertools import batched
from utils.models import (
    User, Premium, Auth, Blacklist, Settings,
    Stats, Member, Punishment, Key, Backup)
from utils.time import now
from utils.enums import RowStatus, KeyType
from utils.backup import BackupData
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Any, Literal, overload, TYPE_CHECKING
from app_types import DatabaseConfig, UserModel, AuthModel, SettingModel
if TYPE_CHECKING:
    from utils.state import State

log = logging.getLogger('fluc')
DEV = os.getenv('DEV', False)


class DBSnippets:
    @staticmethod
    @functools.cache
    def _load(snippet: str, mode: str) -> str:
        with open(f'snippets/db_snippets/{snippet}/{mode}.sql') as file:
            content = file.read()
        return content
        
    @classmethod
    def user(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('users', mode)

    @classmethod
    def blacklist(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('blacklist', mode)
    
    @classmethod
    def auths(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('auths', mode)
    
    @classmethod
    def settings(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('settings', mode)
    
    @classmethod
    def stats(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('stats', mode)
        
    @classmethod
    def punishments(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('punishments', mode)
        
    @classmethod
    def keys(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('keys', mode)
        
    @classmethod
    def fuck_ai(cls, mode: Literal['get', 'set', 'del', 'get_all'], /):
        return cls._load('fuck_ai', mode)

    @classmethod
    def managed_keys(cls, mode: Literal['set', 'get'], /):
        return cls._load('managed_keys', mode)

    @classmethod
    def backups(cls, mode: Literal['get', 'set', 'del'], /):
        return cls._load('backups', mode)


class Database:
    def __init__(self, State: type[State]):
        self.closed = True
        self.pool: Optional[aiomysql.Pool] = None
        self.State = State
        self.__config = None

    async def connect(self, db_config: DatabaseConfig):
        # Default MySQL port
        port = db_config.port or 3306
        host = os.getenv('DB_HOST')
        if DEV:
            log.debug('Will not connect to Database (DEV mode)')
            self.pool = None
            self.closed = False
            return
        log.debug(f'Connecting to {db_config.database}@{host}{port}')
        pool = await aiomysql.create_pool(
            host=host,
            port=port,
            user=os.getenv('DB_USERNAME'),
            password=os.getenv('DB_PASSWORD'),
            db=db_config.database,
            # 1 hour connection
            pool_recycle=3600,
            autocommit=db_config.autocommit or True
        )
        self.__config = db_config
        self.pool = pool
        self.closed = False

    async def init_db(self):
        with open('snippets/db_init.sql') as file:
            snippet = file.read()
        await self.query(snippet)

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.closed = True
        log.info('Database closed')

    async def __aenter__(self):
        if self.closed:
            raise RuntimeError('Database is not open.')
        await self.init_db()

    async def __aexit__(self, *_):
        await self.close()

    async def set_user(self, user: User) -> RowStatus:
        '''
        Adds/updates a user.

        Parameters
        ----------
        user : User
            User with new properties to update.

        Returns
        -------
        :class:`~utils.enums.RowStatus`
            Status of the update.
        '''
        if user.is_elevated:
            # Cannot blacklist an elevated user
            user.blacklist.expires_at = None
        rowcount = await self.query(
            DBSnippets.user('set'),
            (user.id, user.flags.value, user.premium.key, user.restore_credit, user.blacklist.expires_at),
            rowcount=True
        )
        return RowStatus(rowcount)
    
    async def get_user(self, user_id: int, *, with_stats: bool = False) -> Optional[User]:
        '''
        Returns user from database.
        Always returns elevated user on DEV mode.

        Parameters
        ----------
        user_id : int
            ID of user you want to get.

        Returns
        -------
        Optional[:class:`~utils.User`]
            User if it was found in the database.
        '''
        if DEV:
            return User.new(State, user_id, is_super=True)
        data = await self.query(
            DBSnippets.user('get'),
            (user_id,),
            fetchall=False
        )
        if data:
            model = UserModel.model_validate(data)
            premium = None
            if model.premium_key:
                key = await self.get_key(model.premium_key)
                if key and key.redeemed_at:
                    expires = key.redeemed_at + timedelta(days=key.value)
                    premium = Premium(key.key, expires)
            auth = await self.get_auth(user_id)
            settings = await self.get_settings(user_id)
            stats = None
            if with_stats:
                # Users with large stats get massive command delay
                stats = await self.get_stats(user_id)
            user = User(model, self.State, settings, auth, stats, premium)
            return user

    async def del_user(self, user_id: int) -> bool:
        '''
        Deletes user from database.

        Parameters
        ----------
        user_id : int
            ID of the user to delete.

        Returns
        -------
        bool
            Whether the user was deleted.
        '''
        user = await self.get_user(user_id)
        if user:
            if user.is_blacklisted or user.is_limited:
                # Deleting limited/blacklisted users is not allowed
                return False
        rowcount = await self.query(
            DBSnippets.user('del'),
            (user_id,),
            rowcount=True
        )
        return bool(rowcount)

    async def set_premium(self, user: User, expires: Optional[date] = now(weeks=4).date(), *, key_override: Optional[str] = None) -> RowStatus:
        '''
        Adds/updates premium status for a user.

        Parameters
        ----------
        user : int
            User to update.
        expires : Optional[:class:`datetime.date`]
            Datetime when premium shall expire, by default CURRENT_DATE + 4 weeks.

        Returns
        -------
        :class:`~utils.RowStatus`
            Status of the update.
        '''
        if expires:
            key = Key(
                key_override or str(uuid.uuid4()),
                utils.now().date(),
                utils.now(days=30).date(),
                (expires - utils.now().date()).days,
                KeyType.PREMIUM,
                utils.now().date()
            )
            await self.set_key(key)
            premium = Premium(key.key, expires)
        else:
            premium = Premium(None, None)
        user.premium = premium
        return await self.set_user(user)

    async def del_premium(self, user: User) -> bool:
        key = await self.get_managed_key(user.id)
        if key:
            return await self.del_key(key.key)
        return False

    async def set_blacklist(self, user_id: int, expires: Optional[date] = now(weeks=1).date()) -> RowStatus:
        '''
        Adds/updates blacklist status for a user.

        Parameters
        ----------
        user_id : int
            ID of user.
        expires : Optional[:class:`datetime.date`]
            Datetime when premium shall expire, by default CURRENT_DATE + 1 weeks.

        Returns
        -------
        :class:`~utils.RowStatus`
            Status of the update.
        '''
        rowcount = await self.query(
            DBSnippets.blacklist('set'),
            (user_id, expires),
            rowcount=True
        )
        return RowStatus(rowcount)

    async def get_blacklist(self, user_id: int) -> Optional[Blacklist]:
        '''
        Returns blacklist status of a user.
        It is recommended to use :attr:`~utils.User.blackist` of
        :meth:`~utils.Database.get_user` for this purpose.

        Parameters
        ----------
        user_id : int
            ID of the user.

        Returns
        -------
        Optional[:class:`~utils.Blacklist`]
            Blacklist status of user.
            If `None` was returned, the user does not exist.
        '''
        result = await self.query(
            DBSnippets.blacklist('get'),
            (user_id,),
            fetchall=False
        )
        if not result:
            return None
        return Blacklist(result['blacklisted_until'])

    async def del_blacklist(self, user_id: int) -> bool:
        '''
        Removes blacklist status from a user.

        Parameters
        ----------
        user_id : int
            ID of user.

        Returns
        -------
        bool
            Whether premium was removed from this user.
            `False` could also mean the user was not found.
        '''
        rowcount = await self.query(
            DBSnippets.blacklist('del'),
            (user_id,),
            rowcount=True
        )
        return bool(rowcount)
    
    async def set_auth(self, auth: Auth) -> RowStatus:
        '''
        Adds/updates auth data of a user.

        Parameters
        ----------
        auth : Auth
            Auth data.

        Returns
        -------
        :class:`~utils.RowStatus`
            Status of the row.
        '''
        rowcount = await self.query(
            DBSnippets.auths('set'),
            (auth.user_id, auth.username, auth._avatar, auth.access_token,
             auth.token_type, auth._scope, auth.refresh_token, auth.expires),
            rowcount=True
        )
        return RowStatus(rowcount)
    
    async def get_auth(self, user_id: int) -> Optional[Auth]:
        '''
        Returns auth object.
        It is recommended to use :attr:`~utils.User.auth` of :meth:`~utils.Database.get_user`
        for this purpose.

        Parameters
        ----------
        user_id : int
            ID of user.

        Returns
        -------
        Optional[:class:`~utils.Auth`]
            Auth for the user.
            `None` could also mean the user does not exist.
        '''
        data = await self.query(
            DBSnippets.auths('get'),
            (user_id,),
            fetchall=False
        )
        if data:
            expires: datetime = data['expires']
            # tzinfo was not saved in the database
            expires = expires.replace(tzinfo=timezone.utc)
            model = AuthModel.model_validate(data)
            auth = Auth(model, user_id)
            return auth
        
    async def del_auth(self, user_id: int) -> bool:
        '''
        Deletes auth of a user.

        Parameters
        ----------
        user_id : int
            ID of the user.

        Returns
        -------
        bool
            Whether the auth data was deleted.
        '''
        auth = await self.get_auth(user_id)
        if auth:
            async with aiohttp.ClientSession() as session:
                creds = [
                    os.getenv('VERIFY_ID', ''),
                    os.getenv('VERIFY_SECRET', '')
                ]
                if all(creds):
                    basic_auth = aiohttp.BasicAuth(*creds)
                    url = 'https://discord.com/api/v10/oauth2/token/revoke'
                    data = {
                        'token': auth.access_token,
                        'token_type_hint': 'access_token'
                    }
                    await session.post(url, data=data, auth=basic_auth)
        rowcount = await self.query(
            DBSnippets.auths('del'),
            (user_id,),
            rowcount=True
        )
        return bool(rowcount)

    async def get_settings(self, user_id: int) -> Settings:
        '''
        Returns user settings if exists.

        Parameters
        ----------
        user_id : int
            ID of user.

        Returns
        -------
        :class:`~utils.models.Settings`
            User settings. Replaces missing fields with default settings.
        '''
        result = await self.query(
            DBSnippets.settings('get'),
            (user_id,),
            fetchall=False
        )
        if not result:
            return Settings.default(self.State)
        model = SettingModel.model_validate(result)
        return Settings(model, self.State)
    
    async def set_settings(self, user_id: int, settings: Settings) -> RowStatus:
        '''
        Updates settings for a user.

        Parameters
        ----------
        user_id : int
            ID of user.
        settings : Settings
            New settings.

        Returns
        -------
        :class:`~utils.enums.RowStatus`
            Status of update.
        '''
        rowcount = await self.query(
            DBSnippets.settings('set'),
            (
                user_id, settings._server_name, settings._channel_name,
                settings._message_content, settings._bot_nick, settings._bot_bio,
                settings._bot_avatar, settings._bot_banner, settings._rbot_message, settings._rbot_tts
            ),
            rowcount=True
        )
        return RowStatus(rowcount)
    
    async def del_settings(self, user_id: int) -> bool:
        '''
        Deletes user settings.

        Parameters
        ----------
        user_id : int
            ID of user.

        Returns
        -------
        bool
            Whether the settings were deleted.
        '''
        rowcount = await self.query(
            DBSnippets.settings('del'),
            (user_id,)
        )
        return bool(rowcount)

    async def set_stats(self, user_id: int, server_id: int, member_ids: list[int]) -> bool:
        '''
        Set user stats.

        Parameters
        ----------
        user_id : int
            ID of user.
        server_id : int
            ID of server.
        member_ids : list[int]
            Member IDs.

        Returns
        -------
        bool
            Whether the stats were updated.
        '''
        params = tuple(
            (user_id, server_id, member_id)
            for member_id in member_ids
        )
        rowcount = await self.query(
            DBSnippets.stats('set'),
            params,
            execmany=True,
            rowcount=True               
        )
        return bool(rowcount)

    async def get_stats(self, user_id: int) -> Stats:
        '''
        Returns user stats.

        Parameters
        ----------
        user_id : int
            ID of user.

        Returns
        -------
        :class:`~utils.Stats`
            Object containing user stats.
        '''
        stats = await self.query(
            DBSnippets.stats('get'),
            (user_id,)
        )
        # Do not allow duplicated servers IDs
        server_ids = set()
        # Do not show duplicated members
        member_ids = set()
        members = []
        for row in stats:
            member_id = row['member_id']
            server_id = row['server_id']
            server_ids.add(server_id)
            if member_id not in member_ids:
                member = Member(member_id, server_id)
                members.append(member)
            member_ids.add(member_id)
        return Stats(user_id, members, list(server_ids))

    async def del_stats(self, user_id: int, server_id: int) -> bool:
        '''
        Deletes stats from a user.

        Parameters
        ----------
        user_id : int
            ID of user.
        server_id : int
            Server to purge.

        Returns
        -------
        bool
            Whether the user's stats were affected.
        '''
        rowcount = await self.query(
            DBSnippets.stats('del'),
            (user_id, server_id),
            rowcount=True
        )
        return bool(rowcount)

    async def get_punishment(self, punishment_id: int) -> Optional[Punishment]:
        result = await self.query(
            DBSnippets.punishments('get'),
            (punishment_id,),
            fetchall=False
        )
        if not result:
            return
        result['id'] = result.pop('punishment_id')
        result['moderator_id'] = result.pop('user_id')
        result['user_id'] = result.pop('target_user_id')
        result['done_at'] = result.pop('done_at').replace(tzinfo=timezone.utc)
        return Punishment(**result)

    async def get_punishments(self, user_id: int) -> list[Punishment]:
        rows = await self.query(
            'SELECT * FROM punishments WHERE target_user_id=%s',
            (user_id,)
        )
        punishments = []
        for row in rows:
            done_at = row['done_at'].replace(tzinfo=timezone.utc)
            row['done_at'] = done_at
            punishment = Punishment(*row.values())
            punishments.append(punishment)
        return punishments
        
    async def set_punishment(self, punishment: Punishment) -> int:
        result = await self.query(
            DBSnippets.punishments('set'),
            (None, punishment.moderator_id, punishment.user_id,
             punishment.action_id, punishment.executed_action_id, punishment.done_at),
            lastrowid=True
        )
        return result

    async def del_punishment(self, punishment_id: int) -> bool:
        rowcount = await self.query(
            DBSnippets.punishments('del'),
            (punishment_id,),
            rowcount=True
        )
        return bool(rowcount)

    async def get_key(self, key: str) -> Optional[Key]:
        result = await self.query(
            DBSnippets.keys('get'),
            (key,),
            fetchall=False
        )
        if not result:
            return
        return Key(**result)

    async def set_key(self, key: Key) -> RowStatus:
        status = await self.query(
            DBSnippets.keys('set'),
            (key.key, key.issued_at, key.expires_at,
             key.value, key.type, key.redeemed_at),
            rowcount=True
        )
        return RowStatus(status)

    async def del_key(self, key: str) -> bool:
        result = await self.query(
            DBSnippets.keys('del'),
            (key,),
            rowcount=True
        )
        return bool(result)

    async def get_fuck_ai(self, user_id: int) -> bool:
        result = await self.query(
            DBSnippets.fuck_ai('get'),
            (user_id,),
            fetchall=False
        )
        return bool(result)

    async def get_fuck_ai_count(self) -> int:
        result = await self.query(
            DBSnippets.fuck_ai('get_all'),
            fetchall=False
        )
        if not result:
            return 0
        return list(result.values())[0]

    async def set_fuck_ai(self, user_id: int) -> bool:
        rowcount = await self.query(
            DBSnippets.fuck_ai('set'),
            (user_id,),
            rowcount=True
        )
        return bool(rowcount)

    async def del_fuck_ai(self, user_id: int) -> bool:
        rowcount = await self.query(
            DBSnippets.fuck_ai('del'),
            (user_id),
            rowcount=True
        )
        return bool(rowcount)

    async def set_managed_key(self, user_id: int, key: str) -> bool:
        try:
            await self.query(
                DBSnippets.managed_keys('set'),
                (user_id, key)
            )
            return True
        except Exception:
            return False

    async def get_managed_key(self, user_id: int) -> Optional[Key]:
        result = await self.query(
            DBSnippets.managed_keys('get'),
            (user_id,),
            fetchall=False
        )
        if result:
            return await self.get_key(result['key'])

    async def get_backup(self, key: str) -> Optional[Backup]:
        data = await self.query(
            DBSnippets.backups('get'),
            (key,),
            fetchall=False
        )
        if data:
            backup = Backup(**data)
            return backup

    async def set_backup(self, backup: Backup) -> RowStatus:
        data = orjson.dumps(backup).decode()
        rowcount = await self.query(
            DBSnippets.backups('set'),
            (backup.key, backup.created_at, backup.server_id, data),
            rowcount=True
        )
        return RowStatus(rowcount)

    async def del_backup(self, key: str) -> bool:
        rowcount = await self.query(
            DBSnippets.backups('del'),
            (key,),
            rowcount=True
        )
        return bool(rowcount)

    @overload
    async def query(
        self,
        sql: ...,
        params: ... = ...,
        fetchall: Literal[True] = ...,
        execmany: ... = ...
    ) -> tuple[dict[str, Any], ...]:
        ...

    @overload
    async def query(
        self,
        sql: ...,
        params: ... = ...,
        fetchall: Literal[False] = ...,
        execmany: ... = ...
    ) -> Optional[dict[str, Any]]:
        ...

    @overload
    async def query(
        self,
        sql: ...,
        params: ... = ...,
        rowcount: Literal[True] = ...,
        execmany: ... = ...
    ) -> int:
        ...

    @overload
    async def query(
        self,
        sql: ...,
        params: ... = ...,
        lastrowid: Literal[True] = ...,
        execmany: ... = ...
    ) -> int:
        ...

    # Fake ahh error
    async def query( # pyright: ignore[reportInconsistentOverload]
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        fetchall: bool = True,
        rowcount: bool = False,
        execmany: bool = False,
        lastrowid: bool =False
    ) -> ...:
        '''
        Executes SQL query on selected database.

        Parameters
        ----------
        sql : str
            SQL snippet to execute.
        params : tuple[Any, ...], optional
            Parameters of snippet, by default ().
        fetchall : Optional[bool]
            Whether to return all rows (on select), by default True.
        rowcount : Optional[bool]
            Whether to return rowcount, by default False.
        lastrowid : Optional[bool]
            Whether to return last row id, defaults to False.

        Returns
        -------
        int
            Row count.
        ...
            Result of query.

        Raises
        ------
        OSError
            A problem occured while quering.
        '''
        for i in range(2):
            if not self.pool or self.closed:
                if DEV:
                    log.debug(f'Skipping: {sql}{params}')
                    if lastrowid or rowcount:
                        return 0
                    if fetchall:
                        return []
                    return
                if i == 2:
                    log.error('Failed to reconnect. Aborting')
                    return
                self.closed = True
                log.error(f'Connection closed. Could not execute {sql}{params}')
                if not self.__config:
                    # Do not reconnect if database was never open
                    return
                log.info('Attempting to reconnect...')
                await self.connect(self.__config)

        # Parse sql query
        parts = []
        for line in sql.splitlines():
            stripped = line.strip()
            # Might save some KBs of bandwidth every month:)
            if stripped.startswith('--'):
                continue
            parts.append(stripped)
        sql = ' '.join(parts)

        # We did make sure self.pool exists
        async with self.pool.acquire() as conn: # pyright: ignore[reportOptionalMemberAccess]
            conn: aiomysql.Connection
            # Recieve rows as Dict
            rowcount_ = None
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                cursor: aiomysql.DictCursor
                try:
                    if execmany:
                        rowcount_ = 0
                        # constant 1000
                        for batch in batched(params, 1000):
                            await cursor.executemany(sql, batch)
                            rowcount_ += cursor.rowcount
                    else:
                        await cursor.execute(sql, params)
                    log.debug(f'Executed: {sql}{params}')
                except (aiomysql.OperationalError, TypeError) as exc:
                    log.error(f'Error while quering {sql}{params}: {utils.strip_ip(str(exc))}')
                    return
            rowcount_ = rowcount_ or cursor.rowcount
            if rowcount_ is None:
                raise OSError(errno.ENOSPC, 'Disk full.')
            if rowcount:
                return rowcount_ 
            if lastrowid:
                return cursor.lastrowid
            if fetchall:
                return await cursor.fetchall()
            return await cursor.fetchone()
