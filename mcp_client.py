import os
import json
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    def __init__(self):
        self.sessions = {}
        self.exit_stack = AsyncExitStack()
        self.config = None
        self._initialized = False

    async def connect_all(self):
        if self._initialized:
            return
        
        config_path = os.path.join(os.path.dirname(__file__), "mcp_server.json")
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        servers = self.config.get("mcpServers", {})

        for name, server_info in servers.items():
            command = server_info.get("command")
            args = server_info.get("args")

            print(f"🔗 Connecting to {name}: {command} {args}")

            server_params = StdioServerParameters(command=command, args=args, env=None)
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

            await session.initialize()
            self.sessions[name] = session

            response = await session.list_tools()
            print(f"✅ {name} tools:", [tool.name for tool in response.tools])

        self._initialized = True
        print("\n🚀 All servers connected successfully!")

    async def get_all_tools(self):
        if not self._initialized:
            await self.connect_all()
        
        all_tools = {}
        for server_name, session in self.sessions.items():
            response = await session.list_tools()
            all_tools[server_name] = [{
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            } for tool in response.tools]
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        if not self._initialized:
            await self.connect_all()
        
        session = self.sessions.get(server_name)
        if not session:
            raise ValueError(f"Server '{server_name}' not found")
        
        result = await session.call_tool(tool_name, arguments)
        return result.content

    async def cleanup(self):
        await self.exit_stack.aclose()
        self._initialized = False

mcp_client = MCPClient()

async def call_mcp_tool(server_name: str, tool_name: str, arguments: dict):
    return await mcp_client.call_tool(server_name, tool_name, arguments)

if __name__ == "__main__":
    async def main():
        client = MCPClient()
        await client.connect_all()
        tools = await client.get_all_tools()
        print("\nTools:", json.dumps(tools, indent=2))
        await client.cleanup()
    
    asyncio.run(main())
