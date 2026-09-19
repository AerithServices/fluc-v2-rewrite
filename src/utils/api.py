__all__ = (
    'get_ip',
    'load_cookie',
    'dump_cookie',
    'check_redirect',
    'limit_bypass',
    'refresh_user',
    'pull_user'
)

import aiohttp
import os
import utils
from urllib import parse
from utils.core import get_tokens
from utils.state import State
from utils.models import Auth, User
from utils.enums import PullStatus
from fastapi import Request, Response, HTTPException
from itsdangerous import URLSafeSerializer
from http import HTTPStatus
from typing import Optional

def get_ip(request: Request) -> str:    
    cf_header = 'CF-Connecting-IP'
    if cf_header in request.headers:
        # Server is proxies through Cloudflare
        return request.headers[cf_header]
    if not request.client:
        # Should be unreachable
        return str(request.session)
    # Server is not proxied through Cloudflare
    return request.client.host

def limit_bypass(request: Request) -> bool:
    if 'authorization' in request.headers:
        authorization = request.headers['authorization']
        authorization = authorization.removeprefix('Bot').strip()
        if authorization in get_tokens():
            return True
    return False

def load_cookie(
    request: Request,
    cookie_name: str,
    serializer: URLSafeSerializer
) -> Optional[str]:
    cookie = request.cookies.get(cookie_name)
    if cookie:
        try:
            return serializer.loads(cookie)
        except Exception:
            pass

def dump_cookie(
    response: Response,
    cookie_name: str,
    serializer: URLSafeSerializer,
    data: str,
    **kwargs
):
    if not 'expires' in kwargs:
        kwargs['expires'] = 60 * 60 * 24 * 360
    response.set_cookie(
        cookie_name,
        serializer.dumps(data),
        domain='.fluc.lol',
        httponly=True,
        secure=True,
        samesite='lax',
        **kwargs
    )

def check_redirect(redirect: str):
    if not redirect.startswith('/'):
        raise HTTPException(HTTPStatus.BAD_REQUEST, 'Bad redirect uri')
    return 'https://fluc.lol' + redirect

async def refresh_user(user: User) -> User:
    assert user.auth
    async with aiohttp.ClientSession('https://discord.com') as session:
        now = utils.now(seconds=5, reverse=True)
        expires = user.auth.expires
        if not expires.tzinfo:
            now = now.replace(tzinfo=None)
        if expires < now:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': user.auth.refresh_token
            }
            headers = {
                'content-type': 'application/x-www-form-urlencoded'
            }
            data = parse.urlencode(data)
            client_id = State.verify_config.client_id
            auth = aiohttp.BasicAuth(str(client_id), os.getenv('VERIFY_SECRET', ''))
            async with session.post('/api/oauth2/token', data=data, headers=headers, auth=auth) as response:
                if not response.ok:
                    # Most likely deauthed through Discord settings
                    await State.db.del_auth(user.id)
                    user.auth = None
                    return user
                token_data = await response.json()
        else:
            now = utils.now()
            if not expires.tzinfo:
                now = now.replace(tzinfo=None)
            token_data = {
                'token_type': user.auth.token_type,
                'access_token': user.auth.access_token,
                'refresh_token': user.auth.refresh_token,
                'expires_in': (now - user.auth.expires).seconds
            }
        headers = {
            'authorization': f'{token_data['token_type']} {token_data['access_token']}'
        }
        async with session.get('/api/users/@me', headers=headers) as response:
            if response.status is HTTPStatus.UNAUTHORIZED:
                await State.db.del_auth(user.id)
                user.auth = None
                return user
            if not response.ok:
                # Prob rate limited
                return user
            user_data = await response.json()
        auth = Auth.new(
            user,
            username=user_data['username'],
            avatar=user_data.get('avatar'),
            access_token=token_data['access_token'],
            token_type=token_data['token_type'],
            scope='+'.join(State.verify_config.scope),
            refresh_token=token_data['refresh_token'],
            expires=utils.now(seconds=token_data['expires_in'])
        )
        await State.db.set_auth(auth)
        user.auth = auth
        return user
    
async def pull_user(user: User, server_id: int) -> PullStatus:
    if not user.auth:
        return PullStatus.MISSING_AUTH
    headers = { 'Authorization': f'Bot {os.getenv('VERIFY_TOKEN')}' }
    user_ = await refresh_user(user)
    if not user_.auth:
        return PullStatus.MISSING_AUTH
    payload = { 'access_token': user_.auth.access_token }
    async with aiohttp.ClientSession('https://discord.com') as session:
        response = await session.put(f'/api/v9/guilds/{server_id}/members/{user.id}', json=payload, headers=headers)
        if response.status == 201:
            return PullStatus.PULLED
        if response.status == 204:
            return PullStatus.IS_MEMBER
        try:
            data = await response.json()
        except:
            return PullStatus.FAILED
        code = data.get('code')
        if code == 30001:
            return PullStatus.MAX_SERVER_LIMIT
        if response.status == 404:
            return PullStatus.BOT_MISSING
    return PullStatus.FAILED
