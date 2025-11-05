from typing import Dict, List, Optional, Tuple
from tools.toolmanager import handle_tool_call, parse_use_mcp_tool
from prompt.toolPrompt import build_tool_finder_prompt, build_tool_prompt
from utils.createSession import (
    updated_sessions,
    store_message_db,
    extract_memory,
    retrieve_memory_db,
    save_memory_db,
)
import re, json, asyncio


class ToolAgent:
    def __init__(self, session_id: str, api_client, tools_schema, db):
        self.session_id = session_id
        self.api_client = api_client
        self.tools_schema = tools_schema
        self.message_history: List[Dict] = []
        self.result = ""
        self.db = db
        self.context = {}

    def set_context(self, **kwargs):
        """Attach additional runtime data (chat_id, user info, etc.)."""
        self.context.update(kwargs)

    def add_to_history(self, role: str, content: Optional[str]):
        """Track all exchanges for continuity."""
        self.message_history.append({"role": role, "content": content or ""})
        updated_sessions(self.session_id, role, content or "")

    def get_filtered_tool_schema(self, selected_tool_name: str):
        """Return schema slice matching the tool name."""
        if isinstance(self.tools_schema, list):
            for item in self.tools_schema:
                if isinstance(item, dict) and 'tools' in item:
                    tool_info = item['tools']
                    if tool_info.get('name') == selected_tool_name:
                        return [item]
        return []

    async def start_task(self, task: str, conversation_history: Optional[List] = None, mode: Optional[str] = "action") -> str:
        self.result = ""
        self.message_history = []

        user_message = task.strip()
        self.add_to_history("user", f"<task>\n{user_message}\n</task>")

        # Memory management
        try:
            extracted = extract_memory([{"role": "user", "content": user_message}])
            if extracted:
                for field, value in extracted.items():
                    save_memory_db(field, value)
        except Exception as e:
            print(f"⚠️ Memory extraction error: {e}")

        memory_text = retrieve_memory_db(self.db, k=3) or "No memory found."
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in self.message_history[-6:]])
        system_context = f"User memory:\n{memory_text}\n\nRecent history:\n{history_text}"

        # TOOL FINDER
        finder_prompt = await build_tool_finder_prompt(self.tools_schema, memory_text, history_text)
        self.message_history.insert(0, {"role": "system", "content": finder_prompt})

        response = self.api_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.message_history,
            temperature=0.0,
            max_tokens=400,
        )

        finder_output = response.choices[0].message.content.strip()
        print("🧠 Finder Output:", finder_output)

        # Parse tool name
        tool_name, description = "none", ""
        json_match = re.search(r'```json\s*({.*?})\s*```', finder_output, re.DOTALL)
        json_content = json_match.group(1) if json_match else finder_output

        if not json_content.strip().startswith("{"):
            self.result = finder_output
            store_message_db(self.session_id, "assistant", self.result)
            return self.result

        try:
            parsed = json.loads(json_content)
            tool_name = parsed.get("tool_name", "none")
            description = parsed.get("description", "")
        except Exception as e:
            tool_name, description = "none", f"Invalid JSON: {e}"

        if tool_name == "none":
            direct_response = self.api_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are Rouh, a helpful assistant.\n\nUser memory:\n{memory_text}\n\nRecent history:\n{history_text}"},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=200
            )
            self.result = direct_response.choices[0].message.content.strip()
            store_message_db(self.session_id, "assistant", self.result)
            return self.result

        print(f"✅ Tool Selected: {tool_name} — {description}")

        # TOOL EXECUTOR
        filtered_schema = self.get_filtered_tool_schema(tool_name)
        executor_prompt = await build_tool_prompt(filtered_schema)
        
        from prompt.toolPrompt import format_tools_for_finder, format_mcp_tools
        all_local_tools = format_tools_for_finder(self.tools_schema)
        mcp_tools_info = await format_mcp_tools()
        all_tools_info = f"\n\n## ALL AVAILABLE TOOLS:\n{all_local_tools}{mcp_tools_info}"

        self.message_history = [
            {"role": "system", "content": executor_prompt + all_tools_info + "\n\n" + system_context + f"\n\nORIGINAL USER REQUEST: {user_message}\n\nSELECTED FIRST TOOL: {tool_name}\n\n**CRITICAL**: \n1. Use <thinking> to analyze ALL parts of the user's request\n2. IMMEDIATELY start calling tools using <use_mcp_tool> format - do not just describe what you will do\n3. Handle ALL questions/tasks before using <attempt_completion>\n4. Do not explain - just execute the tools"},
            {"role": "user", "content": user_message}
        ]

        # Run executor
        max_iterations = 10
        for i in range(max_iterations):
            ended, result = await self.make_api_requests()
            if ended:
                break
            await asyncio.sleep(0.5)
        else:
            self.result = self.result or "Task completed."

        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    async def make_api_requests(self) -> Tuple[bool, Optional[str]]:
        try:
            response = self.api_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.message_history,
                max_tokens=1000,
                temperature=0.2,
            )
            print('\033[92m=====response=====\033[0m',response)
            assistant_reply = response.choices[0].message.content or "<thinking>Processing...</thinking>"
            print('\033[92m=====assistant_reply=====\033[0m', assistant_reply)

            # Execute tools
            tool_blocks = re.findall(r"<use_mcp_tool>.*?</use_mcp_tool>", assistant_reply, re.DOTALL)
            
            if tool_blocks:
                for xml_tool_call in tool_blocks:
                    tool_call = parse_use_mcp_tool(xml_tool_call)
                    context = getattr(self, 'context', None) or {}
                    result = await handle_tool_call(tool_call, self.db, context)
                    message = result.get("message", "")
                    self.add_to_history("assistant", f"[TOOL OUTPUT]\n{message}")

            # Check completion
            if "<attempt_completion>" in assistant_reply:
                if "</attempt_completion>" in assistant_reply:
                    start = assistant_reply.find("<attempt_completion>") + len("<attempt_completion>")
                    end = assistant_reply.find("</attempt_completion>")
                    content = assistant_reply[start:end].strip()
                    match = re.search(r"<result>(.*?)</result>", content, re.DOTALL)
                    self.result = match.group(1).strip() if match else (content if content else "Task completed successfully.")
                else:
                    # Handle case where only <attempt_completion> is present
                    self.result = "Task completed successfully."
                return True, self.result
            
            if not tool_blocks:
                self.result = assistant_reply.replace("[TOOL OUTPUT]\n", "").strip()
                return True, self.result

            self.add_to_history("assistant", assistant_reply)
            return False, None

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.result = f"Error: {e}"
            return True, self.result