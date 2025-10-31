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
    db = None
    try:
        data = await request.json()
        chat_id = str(data.get("chat_id", ""))
        message = data.get("message", "")
        
        if not chat_id or not message:
            raise HTTPException(status_code=400, detail="Missing chat_id or message")
        
        print(f"📩 Webhook: chat={chat_id}, msg={message[:50]}...")
        
        db = next(get_db())
        
        # Initialize session
        if chat_id not in askControllers.sessions:
            askControllers.sessions[chat_id] = {
                "id": chat_id,
                "name": f"Telegram {chat_id}",
                "messages": []
            }
            
            # Create DB session if needed
            try:
                chat_id_int = int(chat_id)
                if not db.query(Sessions).filter(Sessions.id == chat_id_int).first():
                    db.add(Sessions(id=chat_id_int, name=f"Telegram {chat_id}"))
                    db.commit()
            except ValueError:
                pass
        
        # Get conversation history
        conversation_history = askControllers.sessions[chat_id].get("messages", [])
        store_message_db(session_id=chat_id, role = "user", message =message)
        # Process with agent
        agent = ToolAgent(
            session_id=chat_id,
            api_client=client,
            tools_schema=tools_schema,
            db=db
        )
        response_text = await agent.start_task(message, conversation_history)
        
        print(f"✅ Reply: {response_text[:100]}...")
        return {"reply": response_text}
    
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
