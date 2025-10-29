import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = input("Enter your webhook URL (e.g., https://yourdomain.com/telegram/webhook): ")

async def set_webhook():
    """Set Telegram webhook"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"url": WEBHOOK_URL})
        result = response.json()
        
        if result.get("ok"):
            print(f"✅ Webhook set successfully to: {WEBHOOK_URL}")
        else:
            print(f"❌ Error: {result.get('description')}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
