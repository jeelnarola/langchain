# # telegram_webhook.py
# from telethon import TelegramClient, events
# from datetime import datetime
# from fastapi import FastAPI, Request
# import asyncio, json, os, requests
# from dotenv import load_dotenv

# load_dotenv()

# # Telegram credentials
# API_ID = int(os.getenv("API_ID", "24979612"))
# API_HASH = os.getenv("API_HASH", "fd80348d790f7c10acd4698e73daede1")
# PHONE = os.getenv("PHONE", "+918980672209")

# # Webhook endpoint to forward messages
# WEBHOOK_URL = "http://localhost:8888/webhook/telegram"

# # Initialize Telethon client
# telethon_client = TelegramClient("main_session", API_ID, API_HASH)

# # In-memory message store
# real_time_messages = []

# # FastAPI app
# app = FastAPI(title="Telegram Webhook")


# @telethon_client.on(events.NewMessage)
# async def handle_new_message(event):
#     """Forward new Telegram messages to external webhook"""
#     try:
#         sender = await event.get_sender()
#         chat = await event.get_chat()
        
#         message_data = {
#             "timestamp": datetime.now().isoformat(),
#             "chat_id": chat.id,
#             "chat_name": getattr(chat, "title", getattr(chat, "first_name", "Unknown")),
#             "sender_id": sender.id,
#             "sender_name": getattr(sender, "username", getattr(sender, "first_name", "Unknown")),
#             "text": event.text,
#             "is_outgoing": event.out,
#         }

#         # Save locally
#         real_time_messages.append(message_data)
#         if len(real_time_messages) > 100:
#             real_time_messages.pop(0)

#         # Log to file
#         with open("telethon_messages.log", "a") as f:
#             f.write(json.dumps(message_data) + "\n")

#         print(f"📩 Forwarding message: {message_data['sender_name']} said {event.text}")

#         # Send to webhook (only incoming messages)
#         if not event.out and event.text:
#             try:
#                 print('\033[92m=====WEBHOOK_URL=====\033[0m',WEBHOOK_URL)
#                 response = requests.post(WEBHOOK_URL, json=message_data, timeout=300)
#                 print(f"➡️ Sent to webhook: {response.status_code}")
#             except Exception as e:
#                 print(f"❌ Webhook send error: {e}")

#     except Exception as e:
#         print(f"❌ Message handler error: {e}")


# async def run_telethon():
#     """Start the Telethon client"""
#     await telethon_client.start(phone=PHONE)
#     print("🚀 Telethon client connected.")
#     await telethon_client.run_until_disconnected()


# @app.on_event("startup")
# async def startup_event():
#     """Start Telethon when FastAPI starts"""
#     asyncio.create_task(run_telethon())

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8002)
