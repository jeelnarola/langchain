import os
from fastapi import Request, HTTPException
from dotenv import load_dotenv
from openai import OpenAI
from utils.toolSchema import tools_schema
from utils.toolAgent import ToolAgent
from config.database import get_db
from controllers import askControllers
from model.tableModel import Sessions
from utils.createSession import store_message_db
from whatsapp import send_message  # your existing send_message function

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


async def handle_whatsapp_webhook(request: Request):
    """
    ✅ Handles WhatsApp incoming webhook messages
    ✅ Works similar to handle_telegram_webhook
    ✅ Returns chatbot reply for WhatsApp bridge to send back
    """
    db = None
    try:
        # 1️⃣ Parse incoming data from WhatsApp bridge
        data = await request.json()
        print("\033[92m===== Incoming WhatsApp Data =====\033[0m", data)

        chat_id = str(data.get("chat_id", "")).strip()
        message_id = str(data.get("message_id", "")).strip()
        message_text = str(data.get("message", "")).strip()
        sender_name = str(data.get("sender_name", "") or data.get("sender", "")).strip()

        # 2️⃣ Validate fields
        if not chat_id:
            raise HTTPException(status_code=400, detail="Missing chat_id")
        if not message_text:
            raise HTTPException(status_code=400, detail="Missing message text")

        print(f"📩 WhatsApp message from {sender_name or chat_id}: {message_text}")

        # 3️⃣ Create or load chat session
        db = next(get_db())
        if chat_id not in askControllers.sessions:
            askControllers.sessions[chat_id] = {
                "id": chat_id,
                "name": f"WhatsApp {sender_name or chat_id}",
                "messages": []
            }

            # Store in DB if new
            try:
                if not db.query(Sessions).filter(Sessions.id == chat_id).first():
                    db.add(Sessions(id=chat_id, name=f"WhatsApp {sender_name or chat_id}"))
                    db.commit()
            except Exception as e:
                print(f"⚠️ Session DB check failed: {e}")

        # 4️⃣ Store user message in DB
        store_message_db(session_id=chat_id, role="user", message=message_text)

        # 5️⃣ Get conversation history
        conversation_history = askControllers.sessions[chat_id].get("messages", [])

        # 6️⃣ Initialize AI agent
        agent = ToolAgent(
            session_id=chat_id,
            api_client=client,
            tools_schema=tools_schema,
            db=db
        )

        # 7️⃣ Generate AI response
        response_text = await agent.start_task(message_text, conversation_history)

        # 8️⃣ Save assistant message
        store_message_db(session_id=chat_id, role="assistant", message=response_text)

        # 9️⃣ Send reply back via WhatsApp bridge
        success, result = send_message(chat_id, response_text)
        if not success:
            print(f"❌ Failed to send WhatsApp message: {result}")

        print(f"✅ Replied to {chat_id}: {response_text[:100]}...")

        return {
            "reply": response_text,
            "chat_id": chat_id,
            "message_id": message_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ WhatsApp webhook error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if db:
            db.close()
