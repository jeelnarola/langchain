import os, json, re
from typing import Dict, List, Optional, Tuple
from google import genai
from google.genai import types

# === Local imports ===
from tools.toolmanager import handle_tool_call
from prompt.toolPrompt import build_tool_prompt
from utils.createSession import (
    updated_sessions,
    store_message_db,
    extract_memory,
    retrieve_memory_db,
    save_memory_db,
)
from mcp_client import mcp_client  # ✅ MCP integration

# === Gemini Setup ===
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found in environment!")

client = genai.Client(api_key=api_key)
GEMINI_MODEL = "models/gemini-2.5-flash"


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
    return [gemini_tool]


# ==========================================================
# 🧠 Summarize Chat History
# ==========================================================
async def summarize_chat_history(messages: List[Dict[str, str]], client, model=GEMINI_MODEL, keep_last: int = 20) -> List[Dict[str, str]]:
    """Summarizes old chat messages into a 4–5 line summary, keeps last N full messages."""
    if len(messages) <= keep_last:
        return messages  # Nothing to summarize

    old_messages = messages[:-keep_last]
    recent_messages = messages[-keep_last:]

    text_to_summarize = "\n".join([f"{m['role']}: {m['content']}" for m in old_messages])
    summarize_prompt = (
        "Summarize the following chat conversation into 4-5 lines. "
        "Focus on key topics, actions, and assistant responses.\n\n"
        f"{text_to_summarize}"
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=[types.Part(text=summarize_prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=150,
            ),
        )
        summary_text = response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        print(f"⚠️ Summarization failed: {e}")
        summary_text = "Summary unavailable due to API error."

    summary_message = {
        "role": "system",
        "content": f"🧾 Compressed conversation summary:\n{summary_text}",
    }
    
    print('\033[92m=====summary_message=====\033[0m',summary_message)
    new_history = [summary_message] + recent_messages
    print(f"✅ Summarized {len(old_messages)} messages → kept {len(recent_messages)} recent ones.")
    return new_history


# ==========================================================
# 🤖 ToolAgent — Gemini + MCP + Summarizer
# ==========================================================
class ToolAgent:
    def __init__(self, session_id: str, api_client, tools_schema, db):
        self.session_id = session_id
        self.api_client = api_client
        self.tools_schema = tools_schema or []
        self.message_history: List[Dict] = []
        self.result = ""
        self.db = db

    # -------------------- Logging --------------------
    def add_to_history(self, role: str, content: Optional[str]):
        message = {"role": role, "content": content or ""}
        self.message_history.append(message)
        print("\033[92m=====message=====\033[0m", message)
        updated_sessions(self.session_id, role, content or "")

    # ==========================================================
    # 🚀 Start Task (Summarizer Integrated)
    # ==========================================================
    async def start_task(
        self,
        task: str,
        conversation_history: Optional[List] = None,
        mode: str = "action",
    ) -> str:
        self.result = ""
        self.message_history = conversation_history or []

        # ✅ Add user input
        task_content = f"<task>\n{task}\n</task>"
        self.add_to_history("user", task_content)

        # ✅ Memory extraction
        try:
            extracted = extract_memory([{"role": "user", "content": task}])
            if extracted:
                for field, value in extracted.items():
                    save_memory_db(field, value)
        except Exception as e:
            print(f"❌ Memory extraction failed: {e}")

        # ✅ Compress old chat if long
        if len(self.message_history) > 30:
            self.message_history = await summarize_chat_history(self.message_history, client)

        # ✅ Prepare prompt context
        last_messages = self.message_history[-8:]
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
        memory_text = retrieve_memory_db(self.db, k=3)
        self.system_prompt = await build_tool_prompt(history_text, memory_text)

        # ✅ Run Gemini with tool support
        await self.make_api_requests(task_content)
        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    # ==========================================================
    # ⚙️ Gemini API Request + Auto Function Loop
    # ==========================================================
    async def make_api_requests(self, user_task: str) -> Tuple[bool, Optional[str]]:
        try:
            merged_tools = list(self.tools_schema)

            try:
                mcp_tool_data = await mcp_client.get_all_tools()
                for server_name, tools in mcp_tool_data.items():
                    for tool in tools:
                        schema = tool.get("inputSchema", {"type": "object", "properties": {}})
                        schema = clean_schema(schema)
                        merged_tools.append(
                            {
                                "function": {
                                    "name": tool["name"],
                                    "description": f"[MCP:{server_name}] {tool.get('description', 'No description provided.')}",
                                    "parameters": schema,
                                }
                            }
                        )
                print(f"🧩 Loaded {len(merged_tools)} total tools (local + MCP).")
            except Exception as e:
                print(f"⚠️ Could not load MCP tools: {e}")

            gemini_tools = convert_openai_tools_to_gemini(merged_tools)

            sys_prompt = (
                "\n".join(map(str, self.system_prompt))
                if isinstance(self.system_prompt, list)
                else self.system_prompt
            )

            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=900,
                system_instruction=sys_prompt,
                tools=gemini_tools,
            )

            contents = [types.Content(role="user", parts=[types.Part(text=user_task)])]

            for _ in range(5):
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config,
                )

                print("\033[92m===== GEMINI RAW RESPONSE =====\033[0m", response)

                candidate = response.candidates[0]
                content = candidate.content
                has_function_call = False
                text_parts = []

                for part in content.parts:
                    if part.function_call:
                        has_function_call = True
                        fn_name = part.function_call.name
                        fn_args = part.function_call.args or {}
                        print(f"⚙️ Function call detected: {fn_name}({fn_args})")

                        result = None
                        try:
                            if fn_name in [t["function"]["name"] for t in self.tools_schema]:
                                result = await handle_tool_call(
                                    {"function": {"name": fn_name, "arguments": fn_args}}, self.db
                                )
                            else:
                                for server_name, tools in mcp_tool_data.items():
                                    if any(t["name"] == fn_name for t in tools):
                                        mcp_result = await mcp_client.call_tool(server_name, fn_name, fn_args)
                                        result = {"message": str(mcp_result)}
                                        break
                            if not result:
                                result = {"message": f"Tool '{fn_name}' not found."}
                        except Exception as e:
                            result = {"message": f"❌ Tool execution error: {str(e)}"}

                        tool_result_text = result.get("message", str(result))
                        print(f"✅ Tool result: {tool_result_text}")

                        contents.append(
                            types.Content(
                                role="model",
                                parts=[types.Part(function_call=types.FunctionCall(name=fn_name, args=fn_args))],
                            )
                        )
                        contents.append(
                            types.Content(
                                role="tool",
                                parts=[types.Part(function_response=types.FunctionResponse(name=fn_name, response={"result": tool_result_text}))],
                            )
                        )
                        break  # Re-run Gemini

                    elif part.text:
                        text_parts.append(part.text)

                if not has_function_call:
                    final_text = "\n".join(text_parts).strip()
                    self.result = final_text or "Task completed."
                    print("\033[92m===== GEMINI RESPONSE =====\033[0m", self.result)
                    return True, self.result

            self.result = "⚠️ Reached max function-calling iterations."
            return True, self.result

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result
