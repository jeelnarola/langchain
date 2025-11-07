from fastapi import Request, HTTPException
from mcp_client import call_mcp_tool

# async def handle_mcp_request(request: Request):
#     """Handle MCP server requests"""
#     try:
#         data = await request.json()
#         tool_name = data.get("tool_name")
#         arguments = data.get("arguments", {})
        
#         if not tool_name:
#             raise HTTPException(status_code=400, detail="tool_name is required")
        
        #         result = await call_mcp_tool("my-mcp-project", tool_name, arguments)
#         return {"success": True, "result": result}
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

async def webhook_chat(request: Request):
    data = await request.json()
    print("📩 Webhook received:", data)
    return {"reply": f"Server received: {data.get('message', '')}"}