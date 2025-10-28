#!/usr/bin/env python3
import asyncio
import os
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from typing import Any, Dict, List
import telegram
import json

server = Server("telegram-mcp")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="send_message",
            description="Send a message via Telegram",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["chat_id", "text"]
            }
        ),
        types.Tool(
            name="get_updates",
            description="Get recent Telegram updates",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return [types.TextContent(type="text", text="TELEGRAM_BOT_TOKEN not set")]
    
    bot = telegram.Bot(token=bot_token)
    
    if name == "send_message":
        await bot.send_message(chat_id=arguments["chat_id"], text=arguments["text"])
        return [types.TextContent(type="text", text="Message sent")]
    
    elif name == "get_updates":
        updates = await bot.get_updates()
        return [types.TextContent(type="text", text=json.dumps([u.to_dict() for u in updates[-3:]], indent=2))]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="telegram-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities()
            )
        )

if __name__ == "__main__":
    asyncio.run(main())