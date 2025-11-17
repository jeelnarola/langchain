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
GEMINI_MODEL = "models/gemini-2.5-pro"


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
async def summarize_chat_history(
    messages: List[Dict[str, str]], client, model=GEMINI_MODEL, keep_last: int = 20
) -> List[Dict[str, str]]:
    """Summarizes old chat messages into a 4–5 line summary, keeps last N full messages."""
    if len(messages) <= keep_last:
        return messages  # Nothing to summarize

    old_messages = messages[:-keep_last]
    recent_messages = messages[-keep_last:]

    text_to_summarize = "\n".join(
        [f"{m['role']}: {m['content']}" for m in old_messages]
    )
    summarize_prompt = (
        "Summarize the following chat conversation into 4-5 lines. "
        "Focus on key topics, actions, and assistant responses.\n\n"
        f"{text_to_summarize}"
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(role="user", parts=[types.Part(text=summarize_prompt)])
            ],
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

    print("\033[92m=====summary_message=====\033[0m", summary_message)
    new_history = [summary_message] + recent_messages
    print(
        f"✅ Summarized {len(old_messages)} messages → kept {len(recent_messages)} recent ones."
    )
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
        # print("\033[92m=====message=====\033[0m", message)
        updated_sessions(self.session_id, role, content or "")

    # ==========================================================
    # 🚀 Start Task (Summarizer Integrated) — With Retry Logic
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
        contents = []
        contents = [types.Content(role="user", parts=[types.Part(text=task)])]

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
            self.message_history = await summarize_chat_history(
                self.message_history, client
            )

        # ✅ Prepare prompt context
        last_messages = self.message_history[-8:]
        history_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in last_messages]
        )
        memory_text = retrieve_memory_db(self.db, k=3)
        self.system_prompt = await build_tool_prompt( memory_text)

        await self.make_api_requests(contents)

        store_message_db(self.session_id, "assistant", self.result)
        print("\033[92m===== FINAL RESULT =====\033[0m", self.result)
        return self.result

    # ==========================================================
    # ⚙️ Gemini API Request — Handle Single Part (Append to contents)
    # ==========================================================
    async def make_api_requests(self, contents):
        try:
            merged_tools = list(self.tools_schema or [])

            # ✅ Load MCP tools dynamically
            try:
                mcp_tool_data = await mcp_client.get_all_tools()
                for server_name, tools in mcp_tool_data.items():
                    for tool in tools:
                        schema = tool.get(
                            "inputSchema", {"type": "object", "properties": {}}
                        )
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
                mcp_tool_data = {}

            # ✅ Gemini setup
            gemini_tools = convert_openai_tools_to_gemini(merged_tools)
            sys_prompt = (
                "\n".join(map(str, self.system_prompt))
                if isinstance(self.system_prompt, list)
                else self.system_prompt
            )

            config = types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=1000,
                system_instruction=sys_prompt,
                tools=gemini_tools,
            )

            # 🔹 Prepare base input
            


            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=contents, config=config
            )


            print('\033[92m=====response=====\033[0m',response)

            for candidate in response.candidates:
    # candidate.content.parts is usually a list of text parts
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text and part.text.strip():
                        print(part.text) 
                        return True,part.text
                    if hasattr(part, "function_call") and part.function_call is not None:

                        fn = part.function_call
                        print("Function name:", fn.name)
                        print("Function args:", fn.args)

                        # CORRECT structure
                        tool_call_dict = {
                            "function": {
                                "name": fn.name,
                                "arguments": fn.args
                            }
                        }

                        try:
                            tool_result = await handle_tool_call(tool_call_dict, self.db)
                            print("\033[92m=====tool_result=====\033[0m", tool_result)

                            contents.append(
                                types.Content(
                                    role="tool",
                                    parts=[
                                        types.Part(
                                            function_response=types.FunctionResponse(
                                                name=fn.name,
                                                response=tool_result  # must be dict
                                            )
                                        )
                                    ]
                                )
                            )


                            return False, None

                        except Exception as e:
                            print(f"⚠️ handle_tool_call raised: {e}")
                            return True, f"Tool execution failed: {e}"



            

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result


