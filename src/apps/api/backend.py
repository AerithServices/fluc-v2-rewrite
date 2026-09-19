import uvicorn
import os
import aiohttp
import logging
import orjson
import base64
import hashlib
from utils.state import State
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app_types.config import APIConfig, DatabaseConfig
from itsdangerous import URLSafeSerializer
from .routes import verify, db, account

log = logging.getLogger('fluc')
with open('config/api.json') as file:
    api_config = APIConfig.model_validate_json(file.read())

with open('config/website.json') as file:
    website_config = APIConfig.model_validate_json(file.read())

with open('config/database.json') as file:
    db_config = DatabaseConfig.model_validate_json(file.read())

secret = State.verify_config.model_dump()
secret['token'] = os.getenv('VERIFY_TOKEN', '')
secret['secret'] = os.getenv('VERIFY_SECRET', '')
# We basically put all secrets and config in one dict
# and b64encode it to get the signature. This string
# gets hashed with sha256 as well
json = orjson.dumps(secret)
signature = base64.b64encode(json)
signature = hashlib.sha256(signature).digest()
serializer = URLSafeSerializer(signature, salt=os.getenv('SIGNATURE_SALT'))
# Cleanup
del json, secret

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info('Connecting to database...')
    await State.db.connect(db_config)
    sessions: list[aiohttp.ClientSession] = []
    # sessions.append(await discord.initialize())
    sessions.append(await verify.initialize(serializer))
    await db.initialize(serializer)
    # Run app
    async with State.db:
        yield
    # Clean up
    for session in sessions:
        await session.close()

app = FastAPI(lifespan=lifespan)
app.include_router(verify.router)
app.include_router(db.router)
app.include_router(account.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Fluc DEV endpoints
        'http://127.0.0.1:8008',
        'http://127.0.0.1:8007',
        api_config.domain,
        website_config.domain
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
app.mount('/assets', StaticFiles(directory='assets'))
del website_config

filename = os.path.splitext(os.path.basename(__file__))[0]
uvicorn.run(
    f'apps.api.{filename}:app',
    host=api_config.host,
    port=api_config.port,
    # Disable uvicorn's weird log style
    log_config=None
)