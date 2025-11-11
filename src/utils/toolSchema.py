from mcp_client import mcp_client

local_tools_schema = [
    {
        "type": "tools",
        "tools": {
            "name": "pdf_tool",
            "description": "Search for information in uploaded PDF documents. Use this ONLY when the user asks about document content, personal details, or information that might be in PDFs. Do NOT use for database queries like products, orders, or structured data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's natural language question to search in the uploaded PDF",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "tools",
        "tools": {
            "name": "weather_tool",
            "description": "Get current weather for a given city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Name of the city"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "tools",
        "tools": {
            "name": "send_email_tool",
            "description": "Send an email using SMTP or save it to the database without sending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "The recipient's email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject line of the email.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The plain text body of the email.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["send", "save"],
                        "default": "send",
                        "description": "Choose 'send' to send the email and save it to DB, or 'save' to only store in DB without sending.",
                    },
                },
                "required": ["to_email", "subject", "body"],
            },
        },
    },
]

async def get_tools_schema():
    """Get combined local and MCP server tools"""
    tools = local_tools_schema.copy()
    
    try:
        mcp_tools = await mcp_client.get_all_tools()
        for server_name, server_tools in mcp_tools.items():
            for tool in server_tools:
                # Add server name to tool name for uniqueness
                tool_name = f"{server_name}_{tool['name']}"
                tools.append({
                    "type": "tools",
                    "tools": {
                        "name": tool_name,
                        "description": f"[{server_name}] {tool['description']}",
                        "parameters": tool["inputSchema"],
                    },
                    "server_name": server_name,  # Track for routing
                    "original_tool_name": tool["name"]  # Original name
                })
    except Exception as e:
        print(f"Warning: Could not load MCP tools: {e}")
    
    return tools

# For backward compatibility
tools_schema = local_tools_schema
