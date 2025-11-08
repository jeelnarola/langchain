from fastapi import FastAPI,Request
from controllers.whatappController import handle_whatsapp_webhook

app = FastAPI()

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    return await handle_whatsapp_webhook(request)
