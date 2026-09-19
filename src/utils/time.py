__all__ = (
    'now',
    'parse_datetime'
)

import dateparser
import discord
from datetime import datetime, timedelta, timezone
from typing import Unpack, Optional
from app_types import KWNow

def now(*, reverse: bool = False, **kwargs: Unpack[KWNow]) -> datetime:
    '''
    Returns current time.

    Values specified in kwargs will be added to current time.

    Parameters
    ----------
    reverse : bool
        If True, removes specified values in kwargs from current time
        instead of adding them.
    Returns
    -------
    :class:`datetime.datetime`
        The datetime object representing current time.
    '''
    dt = datetime.now(timezone.utc)
    if kwargs:
        if reverse:
            dt -= timedelta(**kwargs)
        else:
            dt += timedelta(**kwargs)
    return dt

def parse_datetime(text: str, **default) -> Optional[datetime]:
    '''
    Parses ``text`` to datetime.

    Parameters
    ----------
    text : str
        Datetime string.

    Returns
    -------
    Optional[:class:`datetime.datetime`]
        Parsed datetime
    '''
    settings: dateparser._Settings = {
        # Makes formats like "3d" don't go "backwards"
        'PREFER_DATES_FROM': 'future',
        # Convert & return as timezone aware UTC timestamp
        'TIMEZONE': 'UTC',
        'TO_TIMEZONE': 'UTC',
        'RETURN_AS_TIMEZONE_AWARE': True
    }
    dt = dateparser.parse(text, settings=settings) # pyright: ignore[reportArgumentType]
    if not dt:
        if default:
            dt = discord.utils.utcnow() + timedelta(**default)
    return dt