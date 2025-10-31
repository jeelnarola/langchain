from fastapi import APIRouter, Request
from routes.sessionsRoute import sessionRouter
from .documentsRoute import documentsRouter
from .messagesRoute import messageRouter
from .askRoute import askRouter
from .usermemoryRoute import memoryRouter
from .mcpRoute import router as mcpRouter
from .telegramRoute import router as telegramRouter

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

router.include_router(mcpRouter, prefix="/mcp")

router.include_router(telegramRouter, prefix="/telegram")

# Direct chat endpoint
from controllers.telegramController import handle_telegram_webhook

@router.post("/chat")
async def chat_endpoint(request: Request):
    print(111111111111111111111111111111111111111111111111111111)
    """Direct chat endpoint"""
    return await handle_telegram_webhook(request)

