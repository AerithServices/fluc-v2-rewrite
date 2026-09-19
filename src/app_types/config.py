__all__ = (
    'UtilsConfig',
    'LEVEL',
    'BotConfig',
    'APIConfig',
    'DatabaseConfig',
    'VerifyConfig',
    'WebsiteConfig',
    'RoleConfig',
    'EmojiConfig',
    'MassDMConfig'
)

import logging
from pydantic import BaseModel
from typing import Literal, Optional

LEVEL = Literal[
    0, 'NOTSET',
    10, 'DEBUG',
    20, 'INFO',
    30, 'WARNING',
    40, 'ERROR',
    50, 'CRITICAL'
]

class Levels(BaseModel):
    DEBUG: Optional[str] = None
    INFO: Optional[str] = None
    WARNING: Optional[str] = None
    ERROR: Optional[str] = None
    CRITICAL: Optional[str] = None

class Format(BaseModel):
    levels: Levels = Levels()
    time_fmt: Optional[str] = None
    center_level: bool = True

class FileLogging(BaseModel):
    log_level: LEVEL = logging.NOTSET
    file_name: Optional[str] = None

class Logging(BaseModel):
    log_level: LEVEL = logging.NOTSET
    file_logging: FileLogging = FileLogging()
    format: Format = Format()

class UtilsConfig(BaseModel):
    logging: Logging = Logging()

class Premium(BaseModel):
    cooldown_coefficient: Optional[float] = None
    notification_channel_id: Optional[int] = None

class IPv4(BaseModel):
    available_ipv4: Optional[list[Optional[str]]] = []

class HTTP(BaseModel):
    nuke: Optional[IPv4] = None
    raid: Optional[IPv4] = None
    utility: Optional[IPv4] = None

class BotConfig(BaseModel):
    command_prefix: list[str]
    owner_ids: list[int] = []
    protected_servers: list[int] = []
    premium: Premium = Premium()
    http: HTTP

class APIConfig(BaseModel):
    host: str
    port: int
    domain: str

class DatabaseConfig(BaseModel):
    port: Optional[int] = 3306
    database: str
    server: Optional[int] = 1
    autocommit: Optional[bool] = True

class VerifyConfig(BaseModel):
    invite_server: int
    main_server: int
    verify_message: int
    client_id: int
    redirect_uri: str
    join_url: str
    scope: list[str]

class RoleConfig(BaseModel):
    super: int
    moderator: int
    premium: int
    blacklisted: int
    user: int
    rep: Optional[int] = None
    limited: Optional[int] = None

class EmojiConfig(BaseModel):
    upvote: int
    downvote: int
    checkmark: int
    crossmark: int
    premium: int

class MassDMConfig(BaseModel):
    server_id: int
    invite: Optional[str] = None
    manager_token: str
    tokens: list[str]

WebsiteConfig = APIConfig
