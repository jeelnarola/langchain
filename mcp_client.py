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
            try:
                if not server_info.get("is_active", True):
                    print(f"[SKIP] Skipping {name} (inactive)")
                    continue
                    
                command = server_info.get("command")
                args = server_info.get("args")

                print(f"[CONNECT] Connecting to {name}: {command} {args}")

                server_params = StdioServerParameters(command=command, args=args, env=None)
                
                # Add timeout to prevent hanging
                stdio_transport = await asyncio.wait_for(
                    self.exit_stack.enter_async_context(stdio_client(server_params)),
                    timeout=300.0
                )
                stdio, write = stdio_transport
                session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

                await asyncio.wait_for(session.initialize(), timeout=300.0)
                self.sessions[name] = session

                response = await asyncio.wait_for(session.list_tools(), timeout=10.0)
                print(f"[OK] {name} tools:", [tool.name for tool in response.tools])
            except asyncio.TimeoutError:
                print(f"[ERROR] Timeout connecting to {name} (server not responding)")
                continue
            except Exception as e:
                print(f"[ERROR] Failed to connect to {name}: {e}")
                continue
            
        self._initialized = True
        print("\n[SUCCESS] All servers connected successfully!")
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
            raise ValueError(f"Server '{server_name}' not found. Available servers: {list(self.sessions.keys())}")
        
        result = await session.call_tool(tool_name, arguments)
        return result.content
    
    async def format_info(self):
        """Get formatted tool names and descriptions from all MCP servers"""
        if not self._initialized:
            await self.connect_all()

        formatted_tools = []
        for server_name, session in self.sessions.items():
            try:
                response = await session.list_tools()
                for tool in response.tools:
                    tool_name = getattr(tool, "name", "Unknown")
                    description = getattr(tool, "description", "No description available")
                    description = description.replace("\n", " ").replace("  ", " ").strip()
                    formatted_tools.append({
                        "name": tool_name,
                        "description": description or "No description available"
                    })
            except Exception as e:
                print(f"[ERROR] Failed to get tools from {server_name}: {e}")
                continue

        return formatted_tools

   
    async def cleanup(self):
        await self.exit_stack.aclose()
        self._initialized = False

mcp_client = MCPClient()

async def call_mcp_tool(server_name: str, tool_name: str, arguments: dict):
    return await mcp_client.call_tool(server_name, tool_name, arguments)

# if __name__ == "__main__":
#     async def main():
#         client = MCPClient()
#         await client.connect_all()
#         tools = await client.get_all_tools()
#         print("\nTools:", json.dumps(tools, indent=2))
#         await client.cleanup()
    
#     asyncio.run(main())

if __name__ == "__main__":
    async def main():
        client = MCPClient()
        await client.connect_all()
        tools = await client.get_all_tools()
        print("\nTools:", json.dumps(tools, indent=2))
        await client.cleanup()
    
    asyncio.run(main())


