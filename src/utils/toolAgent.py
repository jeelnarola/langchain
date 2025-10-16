from typing import Dict, List, Optional, Tuple
from tools.toolmanager import handle_tool_call, parse_use_mcp_tool
from prompt.toolPrompt import build_tool_prompt
from utils.createSession import (
    updated_sessions,
    store_message_db,
    extract_memory,
    retrieve_memory_db,
    save_memory_db,
)
import re, json
from services.mem0_usage import add_to_mem0, retrieve_mem0  

# Assume memory helpers are available

class ToolAgent:
    def __init__(self, session_id: str, api_client, tools_schema, db):
        self.session_id = session_id
        self.api_client = api_client
        self.tools_schema = tools_schema
        self.message_history: List[Dict] = []
        self.tool_call_error_attempt = 0
        self.result = ""
        self.db = db

    # -------------------- History Logging --------------------
    def add_to_history(
        self,
        role: str,
        content: Optional[str],
        tool_calls: Optional[list] = None,
        tool_call_id: Optional[str] = None,
    ):
        message = {"role": role, "content": content or ""}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if tool_call_id:
            message["tool_call_id"] = tool_call_id

        self.message_history.append(message)
        updated_sessions(self.session_id, role, content or "")

    # -------------------- Start Task --------------------
    async def start_task(
        self, task: str, conversation_history: Optional[List], mode: Optional[str] = "action"
    ) -> str:
        self.result = ""
        self.message_history = []
        self.tool_call_error_attempt = 0
        self.mode = mode

        # Wrap user task
        task_content = f"<task>\n{task}\n</task>"
        self.add_to_history("user", task_content)

        # -------------------- Extract & Save User Info --------------------
        try:
            add_to_mem0(user_id=self.session_id,messages=[{"role": "user", "content": task}])
        except Exception as e:
            print(f"❌ Error extracting memory: {e}")

        # -------------------- Prepare Context --------------------
        last_messages = self.message_history[-8:]  # last 8 messages
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
        memory_text = retrieve_mem0(user_id=self.session_id,question=task) # last 3 saved memory items

        system_context = f"User memory:\n{memory_text}\nRecent history:\n{history_text}"

        if not any(msg["role"] == "system" for msg in self.message_history):
            system_prompt = await build_tool_prompt(self.tools_schema)
            self.message_history.insert(
                0,
                {"role": "system", "content": system_prompt + "\n\n" + system_context},
            )

        # -------------------- Task Loop --------------------
        while True:
            did_end_loop = await self.make_api_requests()
            ended, result = did_end_loop
            if ended:
                print('\033[92m=====result=====\033[0m', result)
                break

        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    # -------------------- API Requests / Tool Execution --------------------
    async def make_api_requests(self) -> Tuple[bool, Optional[str]]:
        try:
            # -------------------- Call LLM --------------------
            response = self.api_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.message_history,
                max_tokens=1000,
                temperature=0.2,
            )
            print('\033[92m=====response=====\033[0m', response)

            assistant_reply = response.choices[0].message.content or "<thinking>Processing...</thinking>"
            print('\033[92m=====assistant_reply=====\033[0m', assistant_reply)

            # -------------------- Execute <use_mcp_tool> blocks --------------------
            tool_blocks = re.findall(r"<use_mcp_tool>.*?</use_mcp_tool>", assistant_reply, re.DOTALL)
            
            for xml_tool_call in tool_blocks:
                tool_call = parse_use_mcp_tool(xml_tool_call)
                print('\033[92m=====tool_call=====\033[0m', tool_call)

                # -------------------- Execute the tool --------------------
                result = await handle_tool_call(tool_call, self.db)
                print('\033[92m=====tool_result=====\033[0m', result)
                message = result.get("message", "")
                self.add_to_history("assistant", f"[TOOL OUTPUT]\n{message}")

            print("✅ All tool calls processed")

            # -------------------- Check for <attempt_completion> --------------------
            if "<attempt_completion>" in assistant_reply and "</attempt_completion>" in assistant_reply:
                start = assistant_reply.find("<attempt_completion>") + len("<attempt_completion>")
                end = assistant_reply.find("</attempt_completion>")
                content = assistant_reply[start:end].strip()
                match = re.search(r"<result>(.*?)</result>", content, re.DOTALL)
                self.result = match.group(1).strip() if match else content
                print("🏁 Completion detected, ending task loop.")
                return True, self.result

            print("✅ Continuing task loop...")
            self.add_to_history("assistant", assistant_reply)
            return False, None

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result
