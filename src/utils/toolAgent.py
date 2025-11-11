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
        self.tools_executed = set()  # Track executed tools

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
            extracted = extract_memory([{"role": "user", "content": task}])
            if extracted:
                for field, value in extracted.items():
                    save_memory_db(field, value)
        except Exception as e:
            print(f"❌ Error extracting memory: {e}")

        # -------------------- Prepare Context --------------------
        last_messages = self.message_history[-8:]  # last 8 messages
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in last_messages])
        memory_text = retrieve_memory_db(self.db,k=3)  # last 3 saved memory items

        system_context = f"User memory:\n{memory_text}\nRecent history:\n{history_text}"

        if not any(msg["role"] == "system" for msg in self.message_history):
            system_prompt = await build_tool_prompt()
            self.message_history.insert(
                0,
                {"role": "system", "content": system_prompt + "\n\n" + system_context},
            )

        # -------------------- Task Loop (Max 5 iterations) --------------------
        max_iterations = 5
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            print(f'\033[93m=====Iteration {iteration}/{max_iterations}=====\033[0m')
            did_end_loop = await self.make_api_requests()
            ended, result = did_end_loop
            if ended:
                print('\033[92m=====result=====\033[0m', result)
                break
        
        if iteration >= max_iterations:
            self.result = "Task completed after maximum iterations."
            print('\033[91m=====Max iterations reached=====\033[0m')

        store_message_db(self.session_id, "assistant", self.result)
        return self.result

    # -------------------- API Requests / Tool Execution --------------------
    async def make_api_requests(self) -> Tuple[bool, Optional[str]]:
        try:
            # Convert tools to OpenAI format and build tool metadata map
            openai_tools = []
            tool_metadata = {}  # Map tool_name -> {server_name, original_tool_name}
            
            if self.tools_schema:
                for item in self.tools_schema:
                    if isinstance(item, dict) and "tools" in item:
                        tool_def = item["tools"]
                        tool_name = tool_def["name"]
                        
                        openai_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": tool_def.get("description", ""),
                                "parameters": tool_def.get("parameters", {})
                            }
                        })
                        
                        # Store metadata for MCP tools
                        if "server_name" in item:
                            tool_metadata[tool_name] = {
                                "server_name": item["server_name"],
                                "original_tool_name": item.get("original_tool_name", tool_name)
                            }

            # -------------------- Call LLM --------------------
            response = self.api_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.message_history,
                tools=openai_tools if openai_tools else None,
                max_tokens=1000,
                temperature=0.2,
            )
            print('\033[92m=====response=====\033[0m', response)

            message = response.choices[0].message
            assistant_reply = message.content or ""
            tool_calls = getattr(message, "tool_calls", None)
            
            print('\033[92m=====assistant_reply=====\033[0m', assistant_reply)
            print('\033[92m=====tool_calls=====\033[0m', tool_calls)

            # Handle OpenAI function calls
            if tool_calls:
                # Check if tools were already executed (prevent duplicates)
                tool_signature = "|".join([f"{tc.function.name}:{tc.function.arguments}" for tc in tool_calls])
                if tool_signature in self.tools_executed:
                    # Tools already executed, request final response without tools
                    self.add_to_history("assistant", "Tools already executed. Provide final summary without calling tools.")
                    return False, None
                
                self.tools_executed.add(tool_signature)
                
                # Add assistant message with tool calls
                self.add_to_history("assistant", assistant_reply, tool_calls=tool_calls)
                
                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    tool_call_id = tool_call.id
                    
                    # Create tool call structure with MCP metadata
                    tool_call_dict = {
                        "function": {
                            "name": function_name,
                            "arguments": function_args
                        }
                    }
                    
                    # Add MCP server info if available
                    if function_name in tool_metadata:
                        tool_call_dict["server_name"] = tool_metadata[function_name]["server_name"]
                        tool_call_dict["function"]["name"] = tool_metadata[function_name]["original_tool_name"]
                    
                    print('\033[92m=====executing_tool=====\033[0m', function_name, function_args)
                    result = await handle_tool_call(tool_call_dict, self.db)
                    print('\033[92m=====tool_result=====\033[0m', result)
                    
                    tool_result_content = result.get("message", str(result))
                    self.add_to_history("tool", tool_result_content, tool_call_id=tool_call_id)
                
                # Continue conversation after tool execution
                return False, None

            # If no tool calls, conversation is complete
            if assistant_reply:
                self.result = assistant_reply
                return True, assistant_reply
            
            return False, None

        except Exception as e:
            print(f"❌ Exception during make_api_requests(): {e}")
            self.result = f"An error occurred: {e}"
            return True, self.result