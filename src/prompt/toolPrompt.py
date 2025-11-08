from datetime import datetime
from mcp_client import mcp_client


# ------------------------ PROMPT 1 ------------------------
def format_tools_for_finder(tools_schema):
    """Format tools to show only name and description for the finder prompt"""
    if isinstance(tools_schema, str):
        return tools_schema

    formatted_tools = "## Available Tools:\n"

    if isinstance(tools_schema, list):
        for item in tools_schema:
            if isinstance(item, dict) and "tools" in item:
                tool_info = item["tools"]
                tool_name = tool_info.get("name", "Unknown")
                description = tool_info.get("description", "No description")
                description = description.replace("\n", " ").replace("  ", " ").strip()
                formatted_tools += f"- **{tool_name}**: {description}\n"

    elif isinstance(tools_schema, dict):
        for tool_name, tool_info in tools_schema.items():
            description = tool_info.get("description", "No description")
            description = description.replace("\n", " ").replace("  ", " ").strip()
            formatted_tools += f"- **{tool_name}**: {description}\n"

    return formatted_tools


async def format_mcp_tools():
    """Get MCP tools using format_info function"""
    try:
        mcp_tools_list = await mcp_client.format_info()
        formatted_mcp = "\n## MCP TOOLS:\n"

        for tool in mcp_tools_list:
            tool_name = tool.get("name", "Unknown")
            description = tool.get("description", "No description")
            description = description.replace("\n", " ").replace("  ", " ").strip()
            formatted_mcp += f"- **{tool_name}**: {description}\n"

        return formatted_mcp
    except Exception as e:
        print(f"\033[91m=====DEBUG: MCP tools error=====\033[0m {e}")
        return ""


# async def format_mcp_tools():
#     """Get MCP tools using format_info function"""
#     try:
#         import sys
#         import os
#         sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
#         from mcp_client import mcp_client

#         mcp_tools = await mcp_client.format_info()
#         formatted_mcp = "\n## MCP TOOLS:\n"

#         for tool in mcp_tools:
#             tool_name = tool.get('name', 'Unknown')
#             description = tool.get('description', 'No description')
#             description = description.replace('\n', ' ').replace('  ', ' ').strip()
#             formatted_mcp += f"- **{tool_name}**: {description}\n"

#         return formatted_mcp
#     except Exception as e:
#         print(f'\033[91m=====DEBUG: MCP tools error=====\033[0m {e}')
#         return ""


async def build_tool_finder_prompt(
    tools_schema: str, user_memory: str = "", recent_history: str = ""
):
    """
    Prompt 1: Detect greetings or find which tool fits the user's request.
    If greeting -> respond directly.
    Else -> output only JSON with tool_name + description.
    """

    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    # Get all tools before building the prompt
    local_tools = format_tools_for_finder(tools_schema)
    mcp_tools_list = await mcp_client.format_info()
    print("\033[92m=====mcp_tools_list=====\033[0m", mcp_tools_list)
    # Format MCP tools as string
    mcp_tools = "\n## MCP TOOLS:\n"
    for tool in mcp_tools_list:
        tool_name = tool.get('name', 'Unknown')
        description = tool.get('description', 'No description')
        description = description.replace('\n', ' ').replace('  ', ' ').strip()
        mcp_tools += f"- **{tool_name}**: {description}\n"

    all_tools = local_tools + mcp_tools

    prompt = f"""
# SYSTEM: Rouh — Tool Finder & Routing Assistant
Identity: Rouh, emotionally-intelligent, human-like, concise, helpful.
Purpose: Detect greetings or route requests to the correct MCP tool.

**IMPORTANT:** 
- If pdf_tool is available and user asks for personal information ("my college", "my name", "my details"), ALWAYS use pdf_tool
- For weather queries, use weather_tool
- For other queries, find the most appropriate tool from the list
- Never skip tool calls when a suitable tool exists


Today's date: {current_date} | Current time: {current_time}

---

## CONNECTED TOOLS
{all_tools}

---

## CONTEXT
### User memory
{user_memory or "No memory available."}

### Recent conversation history
{recent_history or "No conversation history."}

---

# OBJECTIVE
1. Detect message type:
   - If greeting, small talk, or thank-you (e.g. "hi", "hello", "good morning", "how are you", "thanks"):
     → Respond naturally as Rouh — friendly and short — no JSON or tool calls.
   - If asking for personal information and pdf_tool is available:
     → ALWAYS select pdf_tool

2. Output formats:
   - For normal intent:
     ```json
     {{
       "tool_name": "TOOL_NAME",
       "description": "WHY this tool fits the request."
     }}
     ```
   - If no suitable tool found:
     ```json
     {{
       "tool_name": "none",
       "description": "No suitable tool found for this request."
     }}
     ```

3. Never use XML or Markdown.
4. Output ONLY the JSON object (or the plain greeting text).

Now analyze the user's message and respond using the above rules.
"""
    return prompt


# ------------------------ PROMPT 2 ------------------------
async def find_tool_schema(tool_name, tools_schema):
    """Dynamically find schema for a given tool name from MCP servers or local tools,
    and print which MCP server it belongs to (auto-detected)."""

    # --- Check local tools ---
    print(
        "\033[92m==========\==========\==========\==========\033[0m",
    )
    if isinstance(tools_schema, list):
        for item in tools_schema:
            if isinstance(item, dict) and "tools" in item:
                tool_info = item["tools"]
                if tool_info.get("name") == tool_name:
                    print(f"✅ Found '{tool_name}' in local tools.")
                    return tool_info, ""

    # --- Check MCP tools dynamically ---
    try:
        import sys
        import os

        sys.path.insert(
            0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        )
        from mcp_client import mcp_client

        all_mcp_tools = await mcp_client.get_all_tools()

        # Automatically sort MCPs alphabetically (or any order you like)
        for server_name, tools in all_mcp_tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    print(f"✅ Found '{tool_name}' in {server_name} MCP server.")
                    return tool, server_name

        print(f"❌ Tool '{tool_name}' not found in any MCP server.")

    except Exception as e:
        print(f"⚠️ Error finding MCP tool schema: {e}")

    return None, ""


async def build_tool_prompt(tool_name):
    """Build executor prompt with only the selected tool"""
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    from utils.toolSchema import tools_schema

    # Find tool schema
    tool_schema, server_name = await find_tool_schema(tool_name, tools_schema)
    tool_info = tool_schema if tool_schema else f"Tool: {tool_name}"

    prompt = f"""
# SYSTEM: Rouh — Tool Executor
Identity: Rouh, emotionally-intelligent MCP assistant.
Purpose: Execute the selected tool with proper reasoning.

Today's date: {current_date} | Current time: {current_time}

## SELECTED TOOL
{tool_info}

# MULTI-STEP EXECUTION PROTOCOL
**CRITICAL**: Handle ALL parts of the user's request before completing!

**TOOL PRIORITY**:
1. Use LOCAL TOOLS first (weather_tool, pdf_tool, send_email_tool, product_insert_tool)
2. Only use MCP tools (send_message, search-youtube, etc.) if specifically needed

<thinking>
1. Parse the COMPLETE user request for ALL tasks
2. List every task that needs completion
3. Plan which LOCAL tools to use for each task
4. Execute tasks in sequence
Example: "weather in surat? my college name?" = Task 1: weather_tool + Task 2: pdf_tool
</thinking>

<use_mcp_tool>
  <server_name>{server_name}</server_name>  <!-- Use the actual server name from MCP Tools list above, e.g., 'telegram-mcp' -->
  <tool_name>TOOL_NAME</tool_name>
  <arguments>
  <![CDATA[
     {{"parameter": "value"}}
  ]]>
  </arguments>
</use_mcp_tool>

**After each tool execution**: 
1. Check if ALL parts of the original request are completed
2. If YES → IMMEDIATELY use <attempt_completion>
3. If NO → Continue with next tool call

**MANDATORY**: Use <attempt_completion> with proper result as soon as all tasks are done!

<attempt_completion>
<result>
Provide a clear, helpful response summarizing what was accomplished (e.g., "I've sent the weather information to your email" or "The current temperature in Bangalore is 25.6°C and I've emailed this information to you")
</result>
</attempt_completion>
"""
    return prompt
