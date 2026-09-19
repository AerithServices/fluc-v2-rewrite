__all__ = (
    'UserModel',
    'AuthModel',
    'SettingModel',
    'PunishmentModel'
)

from datetime import date, datetime
from pydantic import BaseModel
from typing import Optional

class UserModel(BaseModel):
    user_id: int
    flags: int
    premium_key: Optional[str]
    restore_credits: int
    blacklisted_until: Optional[date]

class AuthModel(BaseModel):
    user_id: int
    username: str
    avatar: Optional[str]
    access_token: str
    token_type: str
    scope: str
    refresh_token: str
    expires: datetime

class SettingModel(BaseModel):
    server_name: Optional[str] = None
    channel_name: Optional[str] = None
    message_content: Optional[str] = None
    bot_nick: Optional[str] = None
    bot_bio: Optional[str] = None
    bot_avatar: Optional[str] = None
    bot_banner: Optional[str] = None
    rbot_message: Optional[str] = None
    rbot_tts: Optional[bool] = None

class PunishmentModel(BaseModel):
    punishment_id: int
    user_id: int
    target_user_id: int
    action_id: int
    done_at: datetime
