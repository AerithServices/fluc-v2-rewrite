import utils
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse, RedirectResponse
from slowapi import Limiter

router = APIRouter(prefix='/account')
limiter = Limiter(key_func=utils.get_ip)

@router.get('/logout')
@limiter.limit('5/minute')
async def logout(request: Request, redirect: Optional[str] = None):
    response = ORJSONResponse({ 'detail': 'Process completed' })
    if redirect:
        redirect = utils.check_redirect(redirect)
        response = RedirectResponse(redirect)
    response.delete_cookie('access', domain='.fluc.lol')
    return response