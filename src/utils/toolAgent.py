import os, json, re, inspect
from typing import Dict, List, Optional, Tuple
from google import genai
from google.genai import types

# === Local imports from your project ===
from tools.toolmanager import handle_tool_call
from prompt.toolPrompt import build_tool_prompt
from utils.createSession import (
    updated_sessions,
    store_message_db,
    extract_memory,
    retrieve_memory_db,
    save_memory_db,
)
from mcp_client import mcp_client

# === Google Gemini client setup ===
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found in environment!")

client = genai.Client(api_key=api_key)
GEMINI_MODEL = "models/gemini-2.5-flash"



# ==========================================================
# 🔧 Helper: convert OpenAI-style → Gemini tools
# ==========================================================
def convert_openai_tools_to_gemini(tools_schema):
    """Convert OpenAI-style tool schema into Gemini-compatible declarations."""
    gemini_tool = types.Tool(function_declarations=[])
    for tool in tools_schema:
        fn = tool["function"]
        gemini_tool.function_declarations.append(
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters", {"type": "object", "properties": {}}),
            )
        )
    return [gemini_tool]


# ==========================================================
# 🤖 ToolAgent Class
# ==========================================================
class ToolAgent:
    def __init__(self, session_id: str, api_client, tools_schema, db):
        self.session_id = session_id
        self.api_client = api_client
        self.tools_schema = tools_schema or []
        self.message_history: List[Dict] = []
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
        print("\033[92m=====message=====\033[0m", message)
        updated_sessions(self.session_id, role, content or "")

    # -------------------- Start Task --------------------
    async def start_task(
        self, task: str, conversation_history: Optional[List] = None, mode: str = "action"
    ) -> str:
        self.result = ""
        self.message_history = []
        self.mode = mode

        # User message
        task_content = f"<task>\n{task}\n</task>"
        self.add_to_history("user", task_content)

        # Memory extraction
        try:
            extracted = extract_memory([{"role": "user", "content": task}])
            if extracted:
                for field, value in extracted.items():
                    save_memory_db(field, value)
        except Exception as e:
            print(f"❌ Memory extraction failed: {e}")

        # Build context (recent history + memory)
        last_messages = self.message_history[-8:]
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
        memory_text = retrieve_memory_db(self.db, k=3)
        system_prompt = await build_tool_prompt(last_messages, history_text, memory_text)

        self.system_prompt = system_prompt
        self.user_input = task_content

        # Run Gemini request
        ended, result = await self.make_api_requests()
        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    # ==========================================================
    # ⚙️  Gemini API Request + Tool Handling
    # ==========================================================
    async def make_api_requests(self) -> Tuple[bool, Optional[str]]:
        try:
            # --- Combine local + MCP tools ---
            merged_tools_schema = list(self.tools_schema)
            try:
                mcp_tool_data = await mcp_client.get_all_tools()
                for server_name, tools in mcp_tool_data.items():
                    for tool in tools:
                        schema = tool.get("inputSchema", {"properties": {}})
                        schema.pop("type", None)
                        merged_tools_schema.append({
                            "name": tool["name"],
                            "description": f"[MCP:{server_name}] {tool.get('description', '')}",
                            "parameters": schema,
                        })
                print(f"🧩 Loaded {len(merged_tools_schema)} tools (local + MCP).")
            except Exception as e:
                print(f"⚠️ Could not load MCP tools: {e}")

            gemini_tools = convert_openai_tools_to_gemini(merged_tools_schema)

            # --- Config with system_instruction + temperature ---
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=900,
                system_instruction=self.system_prompt,
                tools=gemini_tools,
            )

            # --- Build user message ---
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(text=self.user_input)],
                )
            ]

            # --- Generate response ---
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            print("\033[92m===== GEMINI RAW RESPONSE =====\033[0m", response)
            assistant_reply = getattr(response, "text", None) or "Task completed."

            # --- Parse tool_code blocks if model emits them ---
            tool_blocks = re.findall(r'```tool_code\s*\n(.*?)\n```', assistant_reply, re.DOTALL)
            if tool_blocks:
                for block in tool_blocks:
                    try:
                        tool_data = json.loads(block)
                        for call in tool_data.get("tool_calls", []):
                            fn = call.get("function", {})
                            tool_name = fn.get("name")
                            fn_args = fn.get("arguments", {})
                            print("\033[92m=====executing_tool=====\033[0m", tool_name, fn_args)
                            result = await handle_tool_call(
                                {"function": {"name": tool_name, "arguments": fn_args}},
                                self.db,
                            )
                            assistant_reply += f"\n\nTool Result: {result.get('message', str(result))}"
                    except Exception as e:
                        print(f"❌ Tool parsing error: {e}")

            self.result = assistant_reply
            print("\033[92m===== GEMINI RESPONSE =====\033[0m", self.result)
            return True, self.result

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result
