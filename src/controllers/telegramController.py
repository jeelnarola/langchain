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
    try:
        data = await request.json()
        chat_id = data.get("chat_id", "")
        message = data.get("message", "")
        
        # Validate inputs
        if not chat_id or not str(chat_id).strip():
            raise HTTPException(status_code=400, detail="chat_id is required")
        if not message or not message.strip():
            raise HTTPException(status_code=400, detail="message is required")
        if len(message) > 10000:
            raise HTTPException(status_code=400, detail="message too long (max 10000 chars)")
        
        chat_id = str(chat_id).strip()
        message = message.strip()
        
        print(f"Received from chat {chat_id}: {message}")
        
        db = next(get_db())
        
        # Create session in memory if not exists
        if chat_id not in askControllers.sessions:
            askControllers.sessions[chat_id] = {"name": f"Telegram {chat_id}", "messages": []}
            
            # Create session in DB if not exists
            existing = db.query(Sessions).filter(Sessions.id == int(chat_id)).first()
            if not existing:
                new_session = Sessions(id=int(chat_id), name=f"Telegram {chat_id}")
                db.add(new_session)
                db.commit()
        
        context = {"chat_id": int(chat_id)}
        print(f"🎯 Setting context with chat_id: {context}")
        store_message_db(session_id = chat_id, role = "user", message = message)
        # Validate OpenAI API key
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
            
        agent = ToolAgent(session_id=chat_id, api_client=client, tools_schema=tools_schema, db=db)
        agent.context = context  # Set context on agent
        
        try:
            response_text = await agent.start_task(message, conversation_history=[])
        except Exception as api_error:
            print(f"❌ API Error: {api_error}")
            response_text = "Sorry, I'm experiencing connection issues. Please try again later."
        
        print(f"Generated reply: {response_text}")
        return {"reply": response_text}
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")
