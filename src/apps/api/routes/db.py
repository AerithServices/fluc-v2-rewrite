import utils
from utils.state import State
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import ORJSONResponse
from slowapi import Limiter
from http import HTTPStatus
from itsdangerous import URLSafeSerializer
from typing import Optional

async def initialize(serializer_: URLSafeSerializer):
    global serializer
    serializer = serializer_

router = APIRouter(prefix='/db')
serializer: URLSafeSerializer
limiter = Limiter(utils.get_ip)

@router.get('/user')
@router.get('/user/{user_id}')
@limiter.limit('3/second')
async def user(request: Request, user_id: Optional[int] = None):
    access = utils.load_cookie(request, 'access', serializer)
    if user_id:
        user = await State.db.get_user(user_id)
    else:
        if access:
            access = access.strip()
        user = None
        query = 'SELECT * FROM auths WHERE SHA2(access_token, 256) = %s'
        user_ = await State.db.query(query, (access,), fetchall=False)
        if user_:
            user = await State.db.get_user(user_['user_id'])

    if not user:
        response = ORJSONResponse(
            status_code=HTTPStatus.UNAUTHORIZED,
            content={ 'detail': 'Unauthorized' }
        )
        response.delete_cookie(
            key='access',
            domain='.fluc.lol'
        )
        return response
    # Note that as_dict contains only user data,
    # not auth data
    content: dict = user.as_dict
    if access and user.auth and access == utils.sha256(user.auth.access_token):
        auth = user.auth
        data = {
            'user_id': auth.user_id,
            'username': auth.username,
            'avatar': auth.avatar,
            'access_token': auth.access_token,
            'token_type': auth.token_type,
            'scope': auth.scope,
            'refresh_token': auth.refresh_token,
            'expires': int(auth.expires.timestamp())
        }
        content['auth'] = data
    else:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)
    
    content['is_owner'] = user.id in State.owner_ids
    content['is_blacklisted'] = user.is_blacklisted
    date = user.premium.expires_at
    if date:
        content['premium_expires_at'] = datetime.combine(date, datetime.min.time())

    # JavaScript is crying
    content['user_id'] = str(content['user_id'])
    if 'auth' in content:
        content['auth']['user_id'] = str(content['user_id'])
    return ORJSONResponse(content)

@router.delete('/user/{user_id}')
@limiter.limit('1/minute')
async def delete_user(request: Request, user_id: int):
    access = utils.load_cookie(request, 'access', serializer)
    if not access:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)
    user = await State.db.get_user(user_id)
    if not user:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail='User was not found')
    if not user.auth:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)
    hashed = utils.sha256(user.auth.access_token)
    if not user.auth or hashed != access:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)
    if user.is_blacklisted:
        raise HTTPException(HTTPStatus.FORBIDDEN, detail='This user cannot be deleted.')
    await State.db.del_user(user_id)
    content = { 'detail': 'User deleted' }
    response = ORJSONResponse(content)
    response.delete_cookie('access', domain='.fluc.lol')
    return response