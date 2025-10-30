# routes/webhookRoute.py
from fastapi import APIRouter, Request
from controllers.telegramController import handle_telegram_webhook  # ✅ correct file

webhookT = APIRouter()

@webhookT.post("/chat")
async def telegram_chat(request: Request):
    """Simple chat endpoint for telegram"""
    return await handle_telegram_webhook(request)
