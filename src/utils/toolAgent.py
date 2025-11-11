# import os
# import json
# import re
# from typing import Dict, List, Optional, Tuple
# from dotenv import load_dotenv
# from google import genai

# # === Load environment variables ===
# load_dotenv()
# api_key = os.getenv("GEMINI_API_KEY")
# if not api_key:
#     raise ValueError("❌ GEMINI_API_KEY not found in environment!")

# # === Google GenAI client ===
# client = genai.Client(api_key=api_key)
# import os
# import json
# import re
# from typing import Dict, List, Optional, Tuple
# from google import genai

# # Configure Gemini client
# api_key = os.environ.get("GEMINI_API_KEY")
# client = genai.Client(api_key=api_key)

# # === Local imports (from your project) ===
# from utils.toolmanager import handle_tool_call, parse_use_mcp_tool
# from prompt.toolPrompt import build_tool_prompt
# from utils.sessionUtils import (
#     updated_sessions,
#     store_message_db,
#     extract_memory,
#     retrieve_memory_db,
#     save_memory_db,
# )
# from mcpclient import mcp_client


# # ==========================================================
# # 🧩 1. Your OpenAI-style Local Tool Schema
# # ==========================================================
# tools_schema = [
#     {
#         "type": "function",
#         "function": {
#             "name": "weather_tool",
#             "description": "Get current weather for a given city",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "city": {"type": "string", "description": "Name of the city"},
#                 },
#                 "required": ["city"],
#             },
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "send_email_tool",
#             "description": "Send an email or save it to DB.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "to_email": {"type": "string"},
#                     "subject": {"type": "string"},
#                     "body": {"type": "string"},
#                 },
#                 "required": ["to_email", "subject", "body"],
#             },
#         },
#     },
# ]


# # ==========================================================
# # 🧠 2. Conversion Helper (OpenAI → Gemini)
# # ==========================================================
# def convert_openai_tools_to_gemini(tools_schema):
#     """Convert OpenAI-style tools into Gemini-compatible format."""
#     gemini_tools = {"function_declarations": []}
#     for tool in tools_schema:
#         fn = tool["function"]
#         gemini_tools["function_declarations"].append({
#             "name": fn["name"],
#             "description": fn.get("description", ""),
#             "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
#         })
#     return [gemini_tools]


# # ==========================================================
# # 🤖 3. ToolAgent Class
# # ==========================================================
# class ToolAgent:
#     def __init__(self, session_id: str, api_client, tools_schema, db):
#         self.session_id = session_id
#         self.api_client = api_client
#         self.tools_schema = tools_schema or []
#         self.db = db
#         self.message_history: List[Dict] = []
#         self.result = ""

#     # -------------------- Add to History --------------------
#     def add_to_history(
#         self,
#         role: str,
#         content: Optional[str],
#         tool_calls: Optional[list] = None,
#         tool_call_id: Optional[str] = None,
#     ):
#         message = {"role": role, "content": content or ""}
#         if tool_calls:
#             message["tool_calls"] = tool_calls
#         if tool_call_id:
#             message["tool_call_id"] = tool_call_id
#         self.message_history.append(message)
#         updated_sessions(self.session_id, role, content or "")

#     # -------------------- Start Task --------------------
#     async def start_task(
#         self, task: str, conversation_history: Optional[List] = None, mode: Optional[str] = "action"
#     ) -> str:
#         self.result = ""
#         self.message_history = []
#         self.mode = mode

#         # Add user message
#         task_content = f"<task>\n{task}\n</task>"
#         self.add_to_history("user", task_content)

#         # Try extracting memory
#         try:
#             extracted = extract_memory([{"role": "user", "content": task}])
#             if extracted:
#                 for field, value in extracted.items():
#                     save_memory_db(field, value)
#         except Exception as e:
#             print(f"❌ Memory extraction failed: {e}")

#         # Build system + memory context
#         last_messages = self.message_history[-8:]
#         history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
#         memory_text = retrieve_memory_db(self.db, k=3)
#         system_context = f"User memory:\n{memory_text}\nRecent history:\n{history_text}"

#         # Add system prompt if missing
#         if not any(msg["role"] == "system" for msg in self.message_history):
#             system_prompt = await build_tool_prompt()
#             self.message_history.insert(
#                 0, {"role": "system", "content": system_prompt + "\n\n" + system_context}
#             )

#         # Run LLM request
#         ended, result = await self.make_api_requests()
#         store_message_db(self.session_id, "assistant", self.result)
#         return self.result

#     # ==========================================================
#     # ⚙️ 4. Core: Make LLM API Request (Gemini 2.5 Flash)
#     # ==========================================================
#     async def make_api_requests(self) -> Tuple[bool, Optional[str]]:
#         try:
#             # Merge local + MCP tools
#             merged_tools_schema = list(self.tools_schema)
#             try:
#                 mcp_tool_data = await mcp_client.get_all_tools()
#                 for server_name, tools in mcp_tool_data.items():
#                     for tool in tools:
#                         schema = tool.get("inputSchema", {"properties": {}})
#                         schema.pop("type", None)
#                         merged_tools_schema.append({
#                             "name": tool["name"],
#                             "description": f"[MCP:{server_name}] {tool.get('description', 'No description')}",
#                             "parameters": schema,
#                         })
#                 print(f"🧩 Loaded {len(merged_tools_schema)} tools (local + MCP).")
#             except Exception as e:
#                 print(f"⚠️ Could not load MCP tools: {e}")

#             # Convert local schema for Gemini
#             gemini_tools = convert_openai_tools_to_gemini(self.tools_schema)

#             # Build complete prompt with system context and tools
#             system_msg = next((msg["content"] for msg in self.message_history if msg["role"] == "system"), "")
#             user_message = self.message_history[-1]["content"]
            
#             # Create enhanced prompt
#             prompt_parts = []
#             if system_msg:
#                 prompt_parts.append(f"System: {system_msg}")
            
#             prompt_parts.append(f"User: {user_message}")
            
#             if merged_tools_schema:
#                 tools_info = "\n\nAvailable Tools (respond with tool_code format if needed):\n" + json.dumps(merged_tools_schema, indent=2)
#                 prompt_parts.append(tools_info)
            
#             enhanced_message = "\n\n".join(prompt_parts)
            
#             # === Gemini call with tools info ===
#             response = client.models.generate_content(
#                 model="gemini-2.0-flash",
#                 contents=enhanced_message,
#                 config={"temperature": 0.2, "max_output_tokens": 1000}
#             )

#             print("\033[92m===== GEMINI RAW RESPONSE =====\033[0m", response)
#             assistant_reply = response.text if response.text else "Task completed."
            
#             # Parse tool_code blocks
#             tool_blocks = re.findall(r'```tool_code\s*\n(.*?)\n```', assistant_reply, re.DOTALL)
#             if tool_blocks:
#                 for tool_block in tool_blocks:
#                     try:
#                         tool_data = json.loads(tool_block)
#                         tool_calls = tool_data.get('tool_calls', [])
                        
#                         for tool_call_data in tool_calls:
#                             func_data = tool_call_data.get('function', {})
#                             tool_name = func_data.get('name')
#                             arguments = func_data.get('arguments', {})
                            
#                             if tool_name:
#                                 tool_call = {
#                                     "server_name": "",
#                                     "tool_name": tool_name,
#                                     "arguments": arguments
#                                 }
                                
#                                 print("\033[92m=====executing_tool=====\033[0m", tool_call)
#                                 result = await handle_tool_call(tool_call, self.db)
#                                 assistant_reply += f"\n\nTool Result: {result.get('message', str(result))}"
                                
#                     except Exception as e:
#                         print(f"❌ Error parsing tool call: {e}")
            
#             self.result = assistant_reply
#             print("\033[92m===== GEMINI RESPONSE =====\033[0m\n", self.result)
#             return True, self.result



#         except Exception as e:
#             print(f"❌ Exception during make_api_requests(): {e}")
#             self.result = f"An error occurred: {e}"
#             return True, self.result


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
from mcp_client import mcp_client  # ✅ use initialized MCPClient instance
import re, json, inspect

class ToolAgent:
    def __init__(self, session_id: str, api_client, tools_schema, db):
        self.session_id = session_id
        self.api_client = api_client
        self.tools_schema = tools_schema  # local tools schema
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
        print('\033[92m=====message=====\033[0m',message)
        updated_sessions(self.session_id, role, content or "")
    
    # -------------------- Start Task --------------------
    async def start_task(
        self, task: str, conversation_history: Optional[List] = None, mode: Optional[str] = "action"
    ) -> str:
        self.result = ""
        self.message_history = []
        self.mode = mode

        # Add user message
        task_content = f"<task>\n{task}\n</task>"
        self.add_to_history("user", task_content)

        # Extract and save memory
        try:
            extracted = extract_memory([{"role": "user", "content": task}])
            if extracted:
                for field, value in extracted.items():
                    save_memory_db(field, value)
        except Exception as e:
            print(f"❌ Memory extraction failed: {e}")
            # Continue without memory extraction

        # Build system context
        last_messages = self.message_history[-8:]
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
        memory_text = retrieve_memory_db(self.db, k=3)
        system_context = f"User memory:\n{memory_text}\nRecent history:\n{history_text}"

        if not any(msg["role"] == "system" for msg in self.message_history):
            system_prompt = await build_tool_prompt()
            self.message_history.insert(
                0, {"role": "system", "content": system_prompt + "\n\n" + system_context}
            )

        # Call LLM once
        ended, result = await self.make_api_requests()
        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    # -------------------- API Request & Tool Handling --------------------
    async def make_api_requests(self) -> Tuple[bool, Optional[str]]:
        try:
            merged_tools_schema = []

            # ✅ Local tools already OpenAI-style
            if self.tools_schema:
                merged_tools_schema.extend(self.tools_schema)

            # ✅ Convert MCP tools into OpenAI tool format
            try:
                mcp_tool_data = await mcp_client.get_all_tools()
                for server_name, tools in mcp_tool_data.items():
                    for tool in tools:
                        schema = tool.get("inputSchema", {"type": "object", "properties": {}})
                        
                        # Ensure valid schema structure
                        if not isinstance(schema, dict):
                            schema = {"type": "object", "properties": {}}
                        if "type" not in schema or schema["type"] is None:
                            schema["type"] = "object"
                        if "properties" not in schema:
                            schema["properties"] = {}
                            
                        merged_tools_schema.append({
                            "type": "function",
                            "function": {
                                "name": tool["name"],
                                "description": f"[MCP:{server_name}] {tool.get('description', 'No description provided.')}",
                                "parameters": schema,
                            }
                        })
                print(f"🧩 Loaded {len(merged_tools_schema)} total tools (local + MCP).")
            except Exception as e:
                print(f"⚠️ Could not load MCP tools: {e}")

            # ✅ Ensure all tools have correct structure
            for i, t in enumerate(merged_tools_schema):
                if "type" not in t or t["type"] != "function":
                    print(f"⚠️ Tool {i} missing type — auto-fixed.")
                    merged_tools_schema[i] = {
                        "type": "function",
                        "function": t.get("function", t)  # fallback
                    }

            # ✅ Make the first OpenAI call
            response = self.api_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.message_history,
                tools=merged_tools_schema,
                temperature=0.2,
                max_tokens=1000,
            )

            message = response.choices[0].message
            assistant_reply = message.content or ""
            tool_calls = getattr(message, "tool_calls", None)

            print("\033[92m=====assistant_reply=====\033[0m", assistant_reply)
            print("\033[92m=====tool_calls=====\033[0m", tool_calls)

            # ✅ Handle tool calls
            if tool_calls:
                self.add_to_history("assistant", None, tool_calls=tool_calls)
                for tool_call in tool_calls:
                    try:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)
                        tool_call_id = tool_call.id

                        tool_call_obj = {
                            "server_name": "",
                            "tool_name": fn_name,
                            "arguments": fn_args,
                        }

                        print("\033[92m=====executing_tool=====\033[0m", tool_call_obj)

                        # Handle local tools
                        if fn_name in [t["function"]["name"] for t in self.tools_schema]:
                            result = await handle_tool_call(
                                {"function": {"name": fn_name, "arguments": fn_args}}, self.db
                            )
                        else:
                            # Handle MCP tools
                            result = {"message": f"Tool '{fn_name}' not found."}
                            for server_name, tools in mcp_tool_data.items():
                                if any(t["name"] == fn_name for t in tools):
                                    result = await mcp_client.call_tool(server_name, fn_name, fn_args)
                                    result = {"message": str(result)}
                                    break
                        print('\033[92m=====result=====\033[0m',result)
                        self.add_to_history("tool", result.get("message", str(result)), tool_call_id=tool_call_id)
                        
                    except Exception as e:
                        print(f"❌ Tool execution error: {e}")
                        self.add_to_history("tool", f"Error: {str(e)}", tool_call_id=tool_call_id)

                # ✅ Second call with tool results
                final_response = self.api_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=self.message_history,
                    max_tokens=800,
                    temperature=0.2,
                )

                self.result = final_response.choices[0].message.content or "Task completed."
                return True, self.result

            # No tool calls, return assistant reply
            self.result = assistant_reply or "Task completed."
            return True, self.result

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result

