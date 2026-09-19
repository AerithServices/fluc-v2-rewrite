__all__ = (
    'CooldownType',
    'Permissions',
    'RowStatus',
    'PullStatus',
    'PunishmentType',
    'KeyType'
)

from enum import IntEnum

class CooldownType(IntEnum):
    USER = 0
    SERVER = 1
    CHANNEL = 2
    GLOBAL = 3

class Permissions(IntEnum):
    PUBLIC = 0
    USER = 1
    PREMIUM = 2
    MOD = 3
    ELEVATED = 4
    OWNER_ONLY = 5

class RowStatus(IntEnum):
    NOT_UPDATED = 0
    CREATED = 1
    UPDATED = 2

class PullStatus(IntEnum):
    PULLED = 0
    IS_MEMBER = 1
    MAX_SERVER_LIMIT = 2
    MISSING_AUTH = 3
    BOT_MISSING = 4
    FAILED = 5

class PunishmentType(IntEnum):
    WARN = 0
    MUTE = 1
    KICK = 2
    BAN = 3
    LIMIT = 4
    BLACKLIST = 5

class KeyType(IntEnum):
    PREMIUM = 0
    RESTORE = 1