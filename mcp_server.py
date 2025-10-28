#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from dotenv import load_dotenv
from tools.toolmanager import weather_tool, pdf_tool, product_insert_tool, send_email_tool, send_telegram_tool

load_dotenv()
app = Server("langchain-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="send_email_tool",
            description="Send an email to a recipient",
            inputSchema={
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email message content"
                    }
                },
                "required": ["to_email", "subject", "body"]
            }
        ),
        Tool(
            name="weather_tool",
            description="Get current weather for a city",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name to get weather for"
                    }
                },
                "required": ["city"]
            }
        ),
        Tool(
            name="pdf_tool",
            description="Search and answer questions from PDF documents",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Question to search in PDF documents"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="product_insert_tool",
            description="Insert a new product into the system",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Product name"
                    },
                    "price": {
                        "type": "number",
                        "description": "Product price"
                    },
                    "description": {
                        "type": "string",
                        "description": "Product description"
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category"
                    }
                },
                "required": ["name", "price", "description"]
            }
        ),
        Tool(
            name="send_telegram_tool",
            description="Send a message to a Telegram chat",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "Telegram chat ID or username (e.g., '@username' or chat ID)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to send"
                    }
                },
                "required": ["chat_id", "message"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "send_email_tool":
            result = send_email_tool(**arguments)
        elif name == "weather_tool":
            result = weather_tool(**arguments)
        elif name == "pdf_tool":
            result = pdf_tool(**arguments)
        elif name == "product_insert_tool":
            result = product_insert_tool(**arguments)
        elif name == "send_telegram_tool":
            result = send_telegram_tool(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        if isinstance(result, dict):
            message = result.get("message", str(result))
        else:
            message = str(result)
            
        return [TextContent(type="text", text=message)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())