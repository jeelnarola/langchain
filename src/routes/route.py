from fastapi import APIRouter, Request, Request
from routes.sessionsRoute import sessionRouter
from .documentsRoute import documentsRouter
from .messagesRoute import messageRouter
from .askRoute import askRouter
from .usermemoryRoute import memoryRouter
from .webhookRoute import webhookT
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="src/page")

@router.get("/")
async def homePage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

router.include_router(sessionRouter, prefix="/sessions")

router.include_router(documentsRouter, prefix="/documents")

router.include_router(askRouter, prefix="/ask")

router.include_router(messageRouter, prefix="/messages")

router.include_router(memoryRouter, prefix="/memory")

router.include_router(webhookT, prefix="/webhook")




