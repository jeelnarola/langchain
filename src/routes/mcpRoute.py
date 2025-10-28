from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from tools.toolmanager import get_all_mcp_tools, call_mcp_tool

router = APIRouter()

class MCPToolCall(BaseModel):
    server_name: str
    tool_name: str
    arguments: Dict[str, Any]

@router.get("/mcp/tools")
async def list_mcp_tools():
    """List all available MCP tools from all servers"""
    try:
        tools = await get_all_mcp_tools()
        return {"status": "success", "tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mcp/call")
async def call_mcp_tool_endpoint(tool_call: MCPToolCall):
    """Call an MCP tool"""
    try:
        result = await call_mcp_tool(
            tool_call.server_name, 
            tool_call.tool_name, 
            tool_call.arguments
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))