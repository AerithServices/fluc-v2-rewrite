import os
import utils
import slowapi
import uvicorn
from app_types import WebsiteConfig
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()
app.mount('/assets', StaticFiles(directory='apps/website/dist/assets'), name='assets')
limiter = slowapi.Limiter(utils.get_ip)

with open('config/website.json') as file:
    website_config = WebsiteConfig.model_validate_json(file.read())

@app.get('/{full_path:path}')
@limiter.limit('10/second')
async def frontend(request: Request):
    if request.url.path == '/sitemap.xml':
        return FileResponse('apps/website/src/sitemap.xml')
    if request.url.path == '/robots.txt':
        return FileResponse('apps/website/src/robots.txt')
    return FileResponse('apps/website/dist/index.html')

filename = os.path.splitext(os.path.basename(__file__))[0]
uvicorn.run(
    f'apps.website.{filename}:app',
    host=website_config.host,
    port=website_config.port,
    log_config=None
)