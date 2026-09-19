from __future__ import annotations
__all__ = (
    'User',
    'Premium',
    'Auth',
    'Blacklist',
    'UserFlags',
    'Stats',
    'Member',
    'Punishment',
    'Key',
    'Backup'
)

import discord
import utils
from utils.backup import BackupData
from utils.flags import Flag, BaseFlags
from utils.enums import KeyType
from abc import ABC, abstractmethod
from colorama import Fore
from datetime import date, datetime
from app_types import UserModel, AuthModel, SettingModel, PunishmentModel
from pydantic import BaseModel as BaseModelpydantic
from dataclasses import dataclass, field
from typing import Union, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from utils.state import State

class BaseModel(ABC):
    _model: BaseModelpydantic

    @classmethod
    @abstractmethod
    def new(cls, *args, **kwargs):
        raise NotImplementedError

    @property
    def as_dict(self) -> dict[str, Union[int, bool]]:
        '''Returns :attr:`_model` as :class:`dict`.'''
        return self._model.model_dump()


class Premium:
    def __init__(self, key: Optional[str], premium_expires_at: Optional[date]) -> None:
        self.key = key
        self.expires_at = premium_expires_at

    @property
    def is_premium(self) -> bool:
        '''Whether user is premium and premium is not expired.'''
        if not self.expires_at:
            return False
        return self.expires_at >= utils.now().date()
    

class Blacklist:
    def __init__(self, blacklist_expires_at: Optional[date]) -> None:
        self.expires_at = blacklist_expires_at

    @property
    def is_blacklisted(self) -> bool:
        '''Whether user is blacklisted and blacklist is not expired.'''
        if not self.expires_at:
            return False
        return self.expires_at > utils.now().date()


class UserFlags(BaseFlags):
    is_super = Flag(0b0001)
    is_private = Flag(0b0010)
    no_data_collection = Flag(0b0100)
    limited = Flag(0b1000)


class User(BaseModel):
    def __init__(self, model: UserModel, State: type[State], settings: Settings, auth: Optional[Auth] = None, stats: Optional[Stats] = None, premium: Optional[Premium] = None):
        self._model = model
        self.id = model.user_id
        self.is_owner = model.user_id in State.owner_ids
        self.flags = utils.UserFlags(model.flags)
        self.restore_credit = model.restore_credits
        self.premium = premium or Premium(None, None)
        self.blacklist = Blacklist(model.blacklisted_until)
        self.auth = None
        if self.is_premium:
            self.settings = settings
        else:
            self.settings = Settings.default(settings._state)
        self._stats: Optional[Stats] = stats
        if auth:
            self._add_auth(auth)

    def _add_auth(self, auth: Auth):
        self.auth = auth
        self.auth.user = self

    @classmethod
    def new(
        cls,
        state: type[State],
        user_id: int,
        settings: Optional[Settings] = None,
        premium: Optional[Premium] = None,
        auth: Optional[Auth] = None,
        blacklist: Optional[Blacklist] = None,
        stats: Optional[Stats] = None,
        is_super: bool = False,
        is_private: bool = False,
        no_data_collection: bool = False,
        restore_credits: int = 0  
    ):
        premium_key = None
        if premium:
            premium_key = premium.key
        if not blacklist:
            blacklist = Blacklist(None)
        flags = utils.UserFlags()
        flags.is_super = is_super
        flags.is_private = is_private
        flags.no_data_collection = no_data_collection
        model = UserModel(
            user_id=user_id,
            flags=flags.value,
            premium_key=premium_key,
            restore_credits=restore_credits,
            blacklisted_until=blacklist.expires_at
        )
        settings = settings or Settings.default(state)
        return cls(model, state, settings, auth, stats, premium)

    @property
    def is_elevated(self) -> bool:
        '''Whether the user is owner or super user.'''
        return self.is_owner or self.flags.is_super

    @property
    def is_private(self) -> bool:
        '''Whether the user's profile is private. Elevated users can't have private profiles.'''
        return not self.is_elevated and self.flags.is_private
    
    @property
    def is_premium(self) -> bool:
        '''
        Alias to :attr:`~utils.Premium.is_premium` and
        :attr:`~utils.User.is_elevated` combined.
        '''
        # Elevated users should also have
        # premium access
        return self.is_elevated or self.premium.is_premium
    
    @property
    def is_blacklisted(self) -> bool:
        '''
        Alias to :attr:`~utils.Blacklist.is_blacklisted` and
        :attr:`~utils.User.is_elevated` combined.
        '''
        return self.is_elevated and False or self.blacklist.is_blacklisted

    @property
    def is_limited(self) -> bool:
        '''
        Alias to :attr:`~utils.models.UserFlags.limited` and
        :attr:`~utils.User.is_elevated` combined.
        '''
        return self.is_elevated and False or self.flags.limited
    
    @property
    def username(self) -> Optional[str]:
        '''Alias to :attr:`~utils.Auth.username`.'''
        if self.auth:
            return self.auth.username
        
    @property
    def avatar(self) -> Optional[str]:
        '''Alias to :attr:`~utils.Auth.avatar`.'''
        if self.auth:
            return self.auth.avatar

    @property
    def stats(self) -> Optional[Stats]:
        if self.is_private:
            return Stats(self.id, [], [])
        return self._stats


class Auth(BaseModel):
    def __init__(self, model: AuthModel, user: Union[User, int]) -> None:
        self._model = model
        if isinstance(user, User):
            self.user = user
            self.user_id = user.id
        else:
            self.user = None
            self.user_id = user
        self.username = model.username
        self._avatar = model.avatar
        self.access_token = model.access_token
        self.token_type = model.token_type
        self._scope = model.scope
        self.refresh_token = model.refresh_token
        self.expires = model.expires

    @classmethod
    def new(
        cls,
        user: Union[User, int],
        username: str,
        avatar: str,
        access_token: str,
        token_type: str,
        scope: str,
        refresh_token: str,
        expires: datetime
    ):
        '''
        Constructs new :class:`utils.Auth`.

        Parameters
        ----------
        user : Union[:class:`~utils.User`, int]
            ID of user or :class:`~utils.User` if available.
        username : str
            Username of user.
        avatar : str
            The user avatar's hash.
        access_token : str
            Access token with available scope provided in ``scope``.
        token_type : str
            Type of token.
        scope : str
            Scope of ``access_token``, must be in format scope1+scope2...
        refresh_token : str
            Refresh token for ``access_token``.
        expires : :class:`datetime.datetime`
            Expiration datetime for ``access_token``.
        '''
        if isinstance(user, User):
            user_id = user.id
        else:
            user_id = user
        model = AuthModel(
            user_id=user_id,
            username=username,
            avatar=avatar,
            access_token=access_token,
            token_type=token_type,
            scope=scope,
            refresh_token=refresh_token,
            expires=expires
        )
        return cls(model, user)

    @property
    def avatar(self) -> str:
        '''Returns :attr:`~utils.Auth._avatar` as URL.'''
        avatar = self._avatar
        base = 'https://cdn.discordapp.com/'
        if not avatar:
            # Is default avatar
            index = (self.user_id >> 22) % 6
            return base + f'embed/avatars/{index}.png'
        url = base + f'avatars/{self.user_id}/'
        if avatar.startswith('_a'):
            # Is animated
            ext = '.gif'
        else:
            ext = '.png'
        url += avatar + ext
        return url
    
    @property
    def avatar_safe(self) -> str:
        '''Unlike :meth:`~utils.Auth.avatar`, **always** returns the URL as .png.'''
        avatar = self.avatar
        if avatar.endswith('.gif'):
            avatar = avatar[:-3] + 'png'
        return avatar

    @property
    def scope(self) -> list[str]:
        '''Returns a list of each scope in :attr:`~utils.Auth._scope`.'''
        return self._scope.split('+')
    

class Settings(BaseModel):
    def __init__(self, model: SettingModel, state: type[State]):
        self._model = model
        self._state = state
        self._server_name = model.server_name
        self._channel_name = model.channel_name
        self._message_content = model.message_content
        self._bot_nick = model.bot_nick
        self._bot_bio = model.bot_bio
        self._bot_avatar = model.bot_avatar
        self._bot_banner = model.bot_banner
        self._rbot_message = model.rbot_message
        self._rbot_tts = model.rbot_tts

    @classmethod
    def new(
        cls,
        state: type[State],
        server_name: Optional[str] = None,
        channel_name: Optional[str] = None,
        message_content: Optional[str] = None,
        bot_nick: Optional[str] = None,
        bot_bio: Optional[str] = None,
        bot_avatar: Optional[str] = None,
        bot_banner: Optional[str] = None,
        rbot_message: Optional[str] = None,
        rbot_tts: Optional[bool] = None
    ) -> Settings:
        model = SettingModel(
            server_name=server_name,
            channel_name=channel_name,
            message_content=message_content,
            bot_nick=bot_nick,
            bot_bio=bot_bio,
            bot_avatar=bot_avatar,
            bot_banner=bot_banner,
            rbot_message=rbot_message,
            rbot_tts=rbot_tts
        )
        return cls(model, state)
    
    @classmethod
    def default(cls, state: type[State]) -> Settings:
        model = SettingModel(
            server_name=None,
            channel_name=None,
            message_content=None
        )
        return cls(model, state)

    def update(
        self,
        server_name: Optional[str] = utils.MISSING,
        channel_name: Optional[str] = utils.MISSING,
        message_content: Optional[str] = utils.MISSING,
        bot_nick: Optional[str] = utils.MISSING,
        bot_bio: Optional[str] = utils.MISSING,
        bot_avatar: Optional[str] = utils.MISSING,
        bot_banner: Optional[str] = utils.MISSING,
        rbot_message: Optional[str] = utils.MISSING,
        rbot_tts: Optional[bool] = utils.MISSING
    ):
        if not server_name is utils.MISSING:
            self._server_name = server_name
        if not channel_name is utils.MISSING:
            self._channel_name = channel_name
        if not message_content is utils.MISSING:
            self._message_content = message_content
        if not bot_nick is utils.MISSING:
            self._bot_nick = bot_nick
        if not bot_bio is utils.MISSING:
            self._bot_bio = bot_bio
        if not bot_avatar is utils.MISSING:
            self._bot_avatar = bot_avatar
        if not bot_banner is utils.MISSING:
            self._bot_banner = bot_banner
        if not rbot_message is utils.MISSING:
            self._rbot_message = rbot_message
        if not rbot_tts is utils.MISSING:
            self._rbot_tts = rbot_tts

    @property
    def server_name(self) -> str:
        return self._server_name or self._state.get_phrase()

    @property
    def channel_name(self) -> str:
        return self._channel_name or self._state.get_phrase()

    @property
    def message_content(self) -> tuple[str, Optional[discord.Embed]]:
        default = (
            '**BEST DISCORD NUKE BOT? CHOOSE [FLUC](https://fluc.lol) **\n'
            '**JOIN TO RECOVER YOUR SERVER**\n'
            'TUTORIAL: https://youtu.be/B1axyjXY54c\n'
            '-# @everyone @here'
        )
        # Basically there's a invisible character (U+FFF4) between the brackets
        # which makes the link look invisible
        default += ' [￴](https://discord.gg/fluc)'
        default_embed = discord.Embed(
            title='_*RAID BY FLUC_',
            description=(
                '```ansi\n'
                f'{Fore.BLUE}Discord: https://discord.gg/fluc\n'
                f'{Fore.RED}YouTube: https://youtube.com/@fluc-discord\n'
                f'{Fore.WHITE}Git: https://git.fluc.lol/fluc\n'
                f'{Fore.CYAN}Site: https://fluc.lol\n'
                '```'
            ),
            color=discord.Color.red()
        )
        default_embed.set_thumbnail(url='https://api.fluc.lol/assets/icons/nuke_glitch.gif')
        message_content = self._message_content
        if message_content:
            if not '@everyone' in message_content:
                # Cuz some forget to put that in the message
                message_content += ' @everyone'
            return message_content, None
        return default, None

    @property
    def bot_nick(self) -> str:
        return self._bot_nick or 'Moddy'

    @property
    def bot_bio(self) -> Optional[str]:
        bio = self._bot_bio
        if bio == -1:
            return None
        return bio or 'Best all-in-one Discord security bot!'

    @property
    def bot_avatar(self) -> Optional[str]:
        avatar = self._bot_avatar
        if avatar == -1:
            return None
        return avatar or 'https://api.fluc.lol/assets/icons/sadcord.png'

    @property
    def bot_banner(self) -> Optional[str]:
        banner = self._bot_banner
        if banner == -1:
            return banner
        return banner or 'https://api.fluc.lol/assets/icons/nuke_wide.png'

    @property
    def rbot_message(self) -> str:
        default = '# BEST R4ID BOT? CHOOSE discord.gg/fluc\n**JOIN FOR BEST DISCORD N4KE TOOLS**\n-# @everyone @here'
        return self._rbot_message or default

    @property
    def rbot_tts(self) -> bool:
        return self._rbot_tts or True


# Easier approach is by using dataclass
# since we do not need any methods
@dataclass(slots=True)
class Member:
    id: int
    server_id: int

@dataclass(slots=True)
class Stats:
    user_id: int
    members: list[Member]
    servers: list[int]

@dataclass(slots=True)
class Punishment:
    id: int
    moderator_id: int
    user_id: int
    action_id: int
    executed_action_id: int
    done_at: datetime

@dataclass(slots=True)
class Key:
    key: str
    issued_at: date
    expires_at: date
    value: int
    type: KeyType
    redeemed_at: Optional[date]

@dataclass(slots=True)
class Backup:
    key: str
    created_at: date
    server_id: int
    data: BackupData