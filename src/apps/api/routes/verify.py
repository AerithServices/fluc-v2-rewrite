import os
import aiohttp
import uuid
import asyncio
import hashlib
import utils
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from itsdangerous import URLSafeSerializer
from fastapi.responses import ORJSONResponse, RedirectResponse
from app_types import WebsiteConfig
from http import HTTPStatus
from slowapi import Limiter
from urllib import parse
from utils.models import User, Auth
from utils.state import State
from utils.enums import PullStatus

router = APIRouter(prefix='/verify')
limiter = Limiter(key_func=utils.get_ip)
session: aiohttp.ClientSession
authorization: aiohttp.BasicAuth
serializer: URLSafeSerializer

with open('config/website.json') as file:
    website_config = WebsiteConfig.model_validate_json(file.read())

def get_error(data: dict):
    return {
        'error': data.get('error'),
        'detail': data.get('error_description')
    }

async def oauth_cleanup():
    next_sleep = 5 * 60
    while True:
        next_sleep_backup = next_sleep
        for state, issued in State.oauth_states.copy().items():
            expires = issued.timestamp() + 5 * 60
            if expires <= utils.now().timestamp():
                State.oauth_states.pop(state)
                continue
            expires_seconds = expires - utils.now().timestamp()
            expires_seconds_min = min(expires_seconds, 3)
            if expires_seconds_min < next_sleep:
                next_sleep = expires_seconds_min
        if next_sleep_backup == next_sleep:
            if next_sleep < 60:
                next_sleep = 5 * 60
        await asyncio.sleep(next_sleep)

async def initialize(serializer_: URLSafeSerializer) -> aiohttp.ClientSession:
    global session
    global authorization
    global serializer
    serializer = serializer_
    session = aiohttp.ClientSession(base_url='https://discord.com/')
    token = os.getenv('UTILITY_TOKEN', '')
    session.headers['authorization'] = f'Bot {token}'

    asyncio.create_task(oauth_cleanup())
    client_id = State.verify_config.client_id
    authorization = aiohttp.BasicAuth(
        str(client_id),
        os.getenv('VERIFY_SECRET', '')
    )
    return session

@router.get('/get-url')
@limiter.limit('5/minute', exempt_when=utils.limit_bypass)
async def join(request: Request, get_bot: Optional[bool] = None, redirect: Optional[str] = None):
    verify_config = State.verify_config
    state = str(uuid.uuid4())
    if redirect:
        utils.check_redirect(redirect)
        state = redirect + '\\' + state
    if get_bot:
        state += 'get_bot'
    State.oauth_states[state] = utils.now()
    params = {
        'client_id': verify_config.client_id,
        'response_type': 'code',
        'redirect_uri': verify_config.redirect_uri,
        'scope': '+'.join(verify_config.scope),
        'state': state,
    }
    params = parse.urlencode(params)
    url = 'https://discord.com/oauth2/authorize?' + params
    content = {
        'url': url,
        'params': params
    }
    return ORJSONResponse(content)

@router.get('/callback')
@limiter.limit('5/minute')
async def callback(
    request: Request,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    code: Optional[str] = None,
    state: Optional[str] = None
):
    verify_config = State.verify_config
    if not state or state not in State.oauth_states:
        detail = f'This link has either been used or is expired, please try again.'
        raise HTTPException(HTTPStatus.FORBIDDEN, detail)

    State.oauth_states.pop(state)
    if error or not code:
        content = {
            'error': error,
            'detail': error_description,
            'code_received': code is not None
        }
        raise HTTPException(HTTPStatus.BAD_REQUEST, content)
    
    # Cuz we have authorization header in default season
    session_temp = aiohttp.ClientSession()
    content = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': verify_config.redirect_uri
    }
    headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
    data = parse.urlencode(content)
    try:
        async with session_temp.post(
            f'{session._base_url}/api/oauth2/token',
            data=data,
            headers=headers,
            auth=authorization
        ) as response:
            token_data = await response.json()
            if not response.ok:
                if isinstance(token_data, dict):
                    content = get_error(token_data)
                    raise HTTPException(HTTPStatus.BAD_REQUEST, content)
    finally:
        await session_temp.close()
    headers = {
        'Authorization': f'{token_data['token_type']} {token_data['access_token']}'
    }
    async with session.get('/api/users/@me', headers=headers) as response:
        if not response.ok:
            if isinstance(token_data, dict):
                content = get_error(token_data) 
                raise HTTPException(HTTPStatus.BAD_REQUEST, content)
        user_data = await response.json()

    user_id = user_data['id']
    user = await State.db.get_user(user_id)
    if not user:
        user = User.new(State, user_id)
        await State.db.set_user(user)
    auth = Auth.new(
        user,
        username=user_data['username'],
        avatar=user_data.get('avatar'),
        access_token=token_data['access_token'],
        token_type=token_data['token_type'],
        scope='+'.join(verify_config.scope),
        refresh_token=token_data['refresh_token'],
        expires=utils.now(seconds=token_data['expires_in'])
    )
    user.auth = auth
    await State.db.set_auth(auth)
    content = { 'detail': 'Process completed' }
    content_ok = content['detail']

    if state.endswith('get_bot'):
        main_server = State.verify_config.main_server
        response = await session.get(f'https://discord.com/api/v9/guilds/{main_server}/members/{user_id}')
        if response.status == HTTPStatus.NOT_FOUND:
            content = { 'detail': 'You must be in the main server to get bot. Join at https://fluc.lol/discord' }
        else:
            invite_server = State.verify_config.invite_server
            status = await utils.pull_user(user, invite_server)
            if status not in (PullStatus.PULLED, PullStatus.IS_MEMBER):
                if status is PullStatus.MAX_SERVER_LIMIT:
                    content = { 'detail': 'YOU HAVE HIT MAX SERVER LIMIT. PLEASE LEAVE 1 SERVER OF YOURS TO GET ADDED TO THE INVITE SERVER.' }
                elif status is PullStatus.BOT_MISSING:
                    content = { 'detail': 'Bot not in invite server. Please let the Fluc staff know about this issue.' }
                else:
                    content = { 'detail': 'Could not add user to server' }

    response = ORJSONResponse(content)
    if content['detail'] == content_ok:
        if state.startswith('/'):
            redirect = state.split('\\')[0]
            response = RedirectResponse(website_config.domain + redirect)
    # Store access_token instead,
    # refresh_token gives permanent access to user account, unless reset
    digest = utils.sha256(auth.access_token)
    utils.dump_cookie(
        response,
        'access',
        serializer,
        digest
    )
    return response
