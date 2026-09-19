__all__ = (
    'test_proxy',
    'test_proxies',
    'make_socket_factory'
)

import logging
import aiohttp
import asyncio
import socket
from app_types.config import IPv4 as IPv4Config
from utils.state import State
from typing import Union, Optional

log = logging.getLogger('fluc')

async def test_proxy(
    proxy: str,
    timeout: Union[float, int] = 5,
    url: str = 'https://discord.com'
) -> bool:
    '''
    Checks if given HTTP proxy is valid.

    Expects proxy in format username:password@host:port.

    Parameters
    ----------
    proxy : str
        Proxy to test.
    timeout : Union[float, int]
        Timeout for proxy in seconds, by default 5.
    url : str
        URL to ping, by default 'https://discord.com'.

    Returns
    -------
    bool
        Whether ``proxy`` is valid and can be used.
    '''
    session = aiohttp.ClientSession()
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    if not proxy.startswith('http://'):
        proxy = 'http://' + proxy
    try:
        resp = await session.get(url, proxy=proxy, timeout=client_timeout)
        await resp.read()
        if resp.ok:
            return True
    except aiohttp.ClientConnectionError:
        pass
    finally:
        await session.close()
    return False

async def test_proxies(
    proxies: list[str],
    timeout: Union[float, int] = 5,
    url: str = 'https://discord.com'
) -> list[str]:
    '''
    Tests a list of proxies.

    Expects proxy in format username:password@host:port.

    Parameters
    ----------
    proxies : list[str]
        List of proxies to test.
    timeout : Union[float, int]
        Timeout for proxy, by default 5
    url : str
        URL to ping, by default 'https://discord.com'

    Returns
    -------
    list[str]
        List of proxies that passed the test.
    '''
    tasks = []
    for proxy in proxies:
        tasks.append(test_proxy(proxy, timeout=timeout, url=url))
    results = await asyncio.gather(*tasks)
    merged = [*zip(results, proxies)]
    passed = []
    for item in merged:
        if item[0]:
            passed.append(item[1])
    return passed

def make_socket_factory(config: Optional[IPv4Config] = None):
    def socket_factory(addr_info: aiohttp.AddrInfoType):
        '''
        Socket factory passed in :class:`aiohttp.TCPConnector` to automatically
        rotate IPv4 addresses when banned from API.
        '''
        family, type_, proto, _, _ = addr_info
        sock = socket.socket(family, type_, proto)
        if source_ip:
            sock.bind((source_ip, 0))
        return sock

    source_ip = None
    if config:
        available_ipv4 = config.available_ipv4
        if not available_ipv4 or not len(available_ipv4):
            source_ip = None
        else:
            index = max(State.nconntries - 1, 0) % (len(available_ipv4) + 1)
            source_ip = available_ipv4[index - 1]
    log.info(f'New TCPConnector using: {source_ip}')
    return socket_factory