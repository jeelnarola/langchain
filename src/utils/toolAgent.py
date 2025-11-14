from typing import Dict, List, Optional, Tuple, Any
from tools.toolmanager import handle_tool_call, parse_use_mcp_tool
from prompt.toolPrompt import build_tool_prompt
from dotenv import load_dotenv
from utils.createSession import (
    updated_sessions,
    store_message_db,
    extract_memory,
    retrieve_memory_db,
    save_memory_db,
)
from mcp_client import mcp_client  
import re
import json
import os
from google import genai
from google.genai import types

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Keep a global client fallback in case ToolAgent wasn't passed an api_client
client = genai.Client(api_key=GEMINI_API_KEY)


# ==========================================================
# 🧹 Schema Cleaner (Unchanged)
# ==========================================================
def clean_schema(schema):
    """Recursively sanitize JSON schema for Gemini tool specs."""
    if isinstance(schema, dict):
        for bad_key in [
            "additional_properties",
            "additionalProperties",
            "examples",
            "nullable",
            "default",
            "title",
            "description",
        ]:
            schema.pop(bad_key, None)

        if "properties" in schema:
            props = schema["properties"]
            if isinstance(props, dict):
                for key, val in list(props.items()):
                    if not isinstance(val, dict):
                        props[key] = {"type": "string", "description": str(val)}
                    else:
                        props[key] = clean_schema(val)
            else:
                schema["properties"] = {}

        if "items" in schema:
            schema["items"] = clean_schema(schema["items"])

        if "required" in schema:
            valid_props = set(schema.get("properties", {}).keys())
            valid_required = [r for r in schema["required"] if r in valid_props]
            if valid_required:
                schema["required"] = valid_required
            else:
                schema.pop("required", None)

        if schema.get("type") not in ["object", "array", "string", "number", "boolean"]:
            schema["type"] = "object"
            schema.setdefault("properties", {})

        schema = {k: v for k, v in schema.items() if v is not None}

    elif isinstance(schema, list):
        return [clean_schema(i) for i in schema]

    return schema


# ==========================================================
# 🔧 Convert OpenAI-style → Gemini tools
# ==========================================================
def convert_openai_tools_to_gemini(tools_schema):
    gemini_tool = types.Tool(function_declarations=[])

    for tool in tools_schema:
        fn = tool.get("function", tool)
        if not isinstance(fn, dict) or "name" not in fn:
            print(f"⚠️ Skipping malformed tool schema: {tool}")
            continue

        clean_params = clean_schema(
            fn.get("parameters", {"type": "object", "properties": {}})
        )
        gemini_tool.function_declarations.append(
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=clean_params,
            )
        )
    print('\033[92m=====gemini_tool=====\033[0m',gemini_tool)
    return [gemini_tool]


class ToolAgent:
    def __init__(self, session_id: str, api_client: Optional[Any], tools_schema: Optional[Dict] = None, db: Optional[Any] = None):
        self.session_id = session_id
        self.api_client = api_client or client
        self.tools_schema = tools_schema or {}
        self.message_history: List[Dict] = []
        self.tool_call_error_attempt = 0
        self.result = ""
        self.context = []
        self.db = db
        self.system_prompt = ""
        self.tools_executed = set()  # Track executed tools
        self.mode = "action"

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
        self, task: str, conversation_history: Optional[List] = None, mode: Optional[str] = "action"
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
            extracted = extract_memory([{"role": "user", "content": task}])
            if extracted:
                for field, value in extracted.items():
                    save_memory_db(field, value)
        except Exception as e:
            print(f"❌ Error extracting memory: {e}")

        # -------------------- Prepare Context --------------------
        last_messages = self.message_history[-8:]  # last 8 messages
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
        memory_text = retrieve_memory_db(self.db, k=3) if self.db is not None else ""

        self.system_prompt = await build_tool_prompt(memory_text)

        # -------------------- Prepare Tools (Once) --------------------
        merged_tools = list(self.tools_schema)
        try:
            from mcp_client import mcp_client
            mcp_tool_data = await mcp_client.get_all_tools()
            for server_name, tools in mcp_tool_data.items():
                for tool in tools:
                    schema = tool.get("inputSchema", {"type": "object", "properties": {}})
                    schema = clean_schema(schema)
                    desc = tool.get('description', 'No description provided.')
                    # Truncate long descriptions to save tokens
                    if len(desc) > 100:
                        desc = desc[:97] + "..."
                    merged_tools.append({
                        "function": {
                            "name": tool["name"],
                            "description": f"[{server_name}] {desc}",
                            "parameters": schema,
                        }
                    })
            print(f"🧩 Loaded {len(merged_tools)} total tools (local + MCP).")
        except Exception as e:
            print(f"⚠️ Could not load MCP tools: {e}")

        # Deduplicate by tool name
        seen_names = set()
        unique_tools = []
        for tool in merged_tools:
            fn = tool.get("function", tool)
            name = fn.get("name")
            if name and name not in seen_names:
                seen_names.add(name)
                unique_tools.append(tool)
        
        gemini_tools = convert_openai_tools_to_gemini(unique_tools)

        # -------------------- Task Loop (Max 5 iterations) --------------------
        max_iterations = 5
        iteration = 0
        conversation_contents = [types.Content(role="user", parts=[types.Part(text=task_content)])]
        
        while iteration < max_iterations:
            iteration += 1
            print(f'\033[93m=====Iteration {iteration}/{max_iterations}=====\033[0m')
            did_end_loop = await self.make_api_requests(conversation_contents, gemini_tools)
            ended, result = did_end_loop
            if ended:
                if result:
                    print('\033[92m=====result=====\033[0m', result)
                break

        if iteration >= max_iterations and not self.result:
            self.result = "Task completed after maximum iterations."
            print('\033[91m=====Max iterations reached=====\033[0m')

        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    # # # -------------------- API Requests / Tool Execution --------------------
    async def make_api_requests(self, conversation_contents: List, gemini_tools: List) -> Tuple[bool, Optional[str]]:
        """
        Returns (ended: bool, result: Optional[str]).
        ended==True means this iteration produced a final result (or error string).
        If tools were invoked and executed, returns (False, None) so caller may continue the loop.
        """

        try:
            # Build config
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=900,
                system_instruction=self.system_prompt,
                tools=gemini_tools
            )
            print('\033[92m=====tools=====\033[0m',gemini_tools)
            print('\033[92m=====config=====\033[0m', config)

            api_client = self.api_client or client

            response = api_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=conversation_contents,
                config=config
            )

            print('\033[92m=====raw_response=====\033[0m', response)

            # Parse Gemini response
            assistant_reply = ""
            function_calls = []

            # Pick the finished candidate (or first as fallback)
            candidates = response.candidates or []
            candidate = None

            for cand in candidates:
                if getattr(cand, "finish_reason", None) == "finish":
                    candidate = cand
                    break

            # Fallback: use first candidate
            if candidate is None and candidates:
                candidate = candidates[0]

            # If still none: retry
            if candidate is None:
                print("No candidates found — retry")
                return False, None

            # Parse candidate parts (same logic as before)
            parts = getattr(candidate, "content", None)
            parts = getattr(parts, "parts", None)

            if parts:
                for part in parts:
                    if getattr(part, "text", None):
                        assistant_reply += part.text
                    elif getattr(part, "function_call", None):
                        function_calls.append(part.function_call)

            # Debug prints
            print('\033[92m=====candidate=====\033[0m', candidate)
            print('\033[92m=====assistant_reply=====\033[0m', assistant_reply)
            print('\033[92m=====function_calls=====\033[0m', function_calls)

            # Empty check
            if not assistant_reply and not function_calls:
                print('\033[91m=====Empty response from Gemini=====\033[0m')
                print(f'\033[91m=====Finish reason: {getattr(candidate, "finish_reason", None)}=====\033[0m')
                self.result = "I apologize, but I couldn't generate a response. Please try again."
                return True, self.result


            # Handle Gemini function calls
            if function_calls:
                self.add_to_history("assistant", assistant_reply)
                
                # Add model response to conversation
                conversation_contents.append(candidate.content)
                
                # Execute tools and add results
                tool_response_parts = []
                for fc in function_calls:
                    function_name = fc.name
                    function_args = dict(fc.args)
                    
                    tool_call_dict = {
                        "function": {
                            "name": function_name,
                            "arguments": function_args
                        }
                    }
                    
                    print('\033[92m=====executing_tool=====\033[0m', function_name, function_args)
                    result = await handle_tool_call(tool_call_dict, self.db)
                    print('\033[92m=====tool_result=====\033[0m', result)
                    
                    tool_result_content = result.get("message", str(result))
                    self.add_to_history("function", tool_result_content)
                    
                    tool_response_parts.append(
                        types.Part(function_response=types.FunctionResponse(
                            name=function_name,
                            response={"result": tool_result_content}
                        ))
                    )
                
                # Add tool results to conversation
                conversation_contents.append(types.Content(role="user", parts=tool_response_parts))
                return False, None

            # If no function calls, conversation is complete
            if assistant_reply:
                self.result = assistant_reply
                return True, assistant_reply
            
            return True, None

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result
        
