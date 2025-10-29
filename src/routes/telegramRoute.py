from fastapi import APIRouter, Request
from controllers.telegramController import handle_telegram_webhook

router = APIRouter()

@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint"""
    return await handle_telegram_webhook(request)

@router.post("/chat")
async def telegram_chat(request: Request):
    """Simple chat endpoint for telegram"""
    return await handle_telegram_webhook(request)