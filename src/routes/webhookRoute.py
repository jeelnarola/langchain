# routes/webhookRoute.py
from fastapi import APIRouter, Request
from controllers.telegramController import handle_telegram_webhook  # ✅ correct file
# from controllers.whatsappHandler import handle_whatsapp_webhook
from controllers.whatsappController import handle_whatsapp_webhook
from controllers.mcpController import webhook_chat
webhookT = APIRouter()

@webhookT.post("/chat")
async def telegram_chat(request: Request):
    """Simple chat endpoint for telegram"""
    return await handle_telegram_webhook(request)

@webhookT.post("/whatsapp")
async def whatsapp_chat(request: Request):
    """Webhook endpoint for whatsapp"""
    return await handle_whatsapp_webhook(request)

@webhookT.post("/mcp")
async def mcp_endpoint(request: Request):
    """Endpoint for MCP server requests"""
    return await webhook_chat(request)


