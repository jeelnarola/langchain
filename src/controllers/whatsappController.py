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

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


async def handle_whatsapp_webhook(request: Request):
    db = None
    try:
        data = await request.json()
        print('\033[92m===== Incoming WhatsApp Data =====\033[0m', data)

        # Extract WhatsApp message fields
        chat_id = str(data.get("chat_id", "")).strip()
        message_text = str(data.get("message", "")).strip()

        if not chat_id or not message_text:
            raise HTTPException(status_code=400, detail="Missing chat_id or message")

        print(f"📩 WhatsApp: chat={chat_id}, msg={message_text[:60]}...")

        # Initialize DB session
        db = next(get_db())

        # Create or retrieve chat session
        if chat_id not in askControllers.sessions:
            askControllers.sessions[chat_id] = {
                "id": chat_id,
                "name": f"WhatsApp {chat_id}",
                "messages": []
            }

            try:
                chat_id_int = int(chat_id)
                if not db.query(Sessions).filter(Sessions.id == chat_id_int).first():
                    db.add(Sessions(id=chat_id_int, name=f"WhatsApp {chat_id}"))
                    db.commit()
            except ValueError:
                pass

        # Get conversation history
        conversation_history = askControllers.sessions[chat_id].get("messages", [])

        # Store the incoming user message
        store_message_db(session_id=chat_id, role="user", message=message_text)

        # Create the agent and process the message
        agent = ToolAgent(
            session_id=chat_id,
            api_client=client,
            tools_schema=tools_schema,
            db=db
        )
        
        # Set context with chat_id for whatsapp tools
        agent.set_context(chat_id=chat_id)

        # Pass message and history for AI reply
        response_text = await agent.start_task(message_text, conversation_history)

        # Log reply and return JSON
        print(f"✅ WhatsApp Reply: {response_text[:100]}...")
        return {
            "reply": response_text,
            "chat_id": chat_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ WhatsApp Webhook error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if db:
            db.close()


async def send_message(to, message):
    """Send WhatsApp message"""
    print(f"[WhatsApp] Sending message to {to}: {message}")
    return {"status": "sent", "to": to, "message": message}