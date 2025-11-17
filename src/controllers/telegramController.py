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


async def handle_telegram_webhook(request: Request):
    """
    ✅ Handles Telegram MCP webhook messages.
    ✅ Builds proper reply context (supports message replies).
    ✅ Uses ToolAgent to process message and returns Telegram-compatible response JSON.
    """

    db = None
    try:
        # 1️⃣ Parse incoming data
        data = await request.json()
        print("\033[92m===== Incoming Telegram MCP Data =====\033[0m", data)

        chat_id = str(data.get("chat_id", "")).strip()
        message_id = str(data.get("message_id", "")).strip()
        message_text = str(data.get("message", "")).strip()
        mention_text = str(data.get("mention_text", "") or data.get("mentionText", "")).strip()

        # 2️⃣ Validate
        if not chat_id:
            raise HTTPException(status_code=400, detail="Missing chat_id")
        if not message_text and not mention_text:
            raise HTTPException(status_code=400, detail="Missing message or mention_text")

        # 3️⃣ Build combined user message
        if mention_text:
            combined_text = (
                "You are a Telegram assistant. "
                "When the user replies to another message, continue that conversation naturally. "
                "Do not ask for technical details like message IDs.\n\n"
                f"User replied to this message:\n🗨️ {mention_text.strip()}\n\n"
                f"User's reply: {message_text.strip()}"
            )
        else:
            combined_text = (
                "You are a Telegram assistant. Respond naturally and conversationally.\n\n"
                + message_text.strip()
            )

        print("\033[93m===== Combined Text =====\033[0m\n", combined_text)

        # 4️⃣ Create or retrieve session from memory/DB
        db = next(get_db())
        if chat_id not in askControllers.sessions:
            askControllers.sessions[chat_id] = {
                "id": chat_id,
                "name": f"Telegram {chat_id}",
                "messages": []
            }
            try:
                chat_id_int = int(chat_id)
                if not db.query(Sessions).filter(Sessions.id == chat_id_int).first():
                    db.add(Sessions(id=chat_id_int, name=f"Telegram {chat_id}"))
                    db.commit()
            except ValueError:
                pass

        # 5️⃣ Save user message (DB + memory)
        store_message_db(session_id=chat_id, role="user", message=message_text)
        askControllers.sessions[chat_id]["messages"].append({"role": "user", "content": message_text})

        # 6️⃣ Retrieve conversation history
        conversation_history = askControllers.sessions[chat_id]["messages"]

        # 7️⃣ Initialize ToolAgent
        agent = ToolAgent(
            session_id=chat_id,
            api_client=client,
            tools_schema=tools_schema,
            db=db
        )

        # 8️⃣ Process with LLM (includes contextual system instruction)
        response_text = await agent.start_task(combined_text, conversation_history)

        # 9️⃣ Save assistant response (DB + memory)
        store_message_db(session_id=chat_id, role="assistant", message=response_text)
        askControllers.sessions[chat_id]["messages"].append({"role": "assistant", "content": response_text})

        # 🔟 Prepare Telegram MCP response
        reply_to_message_id = message_id if mention_text else None

        print(f"✅ Reply for chat={chat_id}, message_id={message_id}: {response_text[:100]}...")

        return {
            "reply": response_text,
            "chat_id": chat_id,
            "reply_to_message_id": reply_to_message_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if db:
            db.close()
