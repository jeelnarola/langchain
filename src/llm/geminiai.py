import google.genai as genai
from typing import List, Dict, Optional
from google.genai import types
from mcp_client import mcp_client
import json

class GeminiClient:
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.client = genai.Client()
        self.model = model
    
    def clean_schema(self, schema: dict) -> dict:
        """Remove unsupported fields from schema"""
        if not isinstance(schema, dict):
            return schema
        
        cleaned = {}
        for key, value in schema.items():
            if key in ['additional_properties', 'additionalProperties']:
                continue
            if isinstance(value, dict):
                cleaned[key] = self.clean_schema(value)
            elif isinstance(value, list):
                cleaned[key] = [self.clean_schema(item) if isinstance(item, dict) else item for item in value]
            else:
                cleaned[key] = value
        return cleaned
    
    

    
    async def merge_tools(self, local_tools: List[Dict]) -> List:
        tools = []
        
        # Add local tools
        if local_tools:
            for tool in local_tools:
                func_decl = genai.types.FunctionDeclaration(
                    name=tool["function"]["name"],
                    description=tool["function"]["description"],
                    parameters=tool["function"]["parameters"]
                )
                tools.append(genai.types.Tool(function_declarations=[func_decl]))
        
        # Add MCP tools
        # try:
        #     mcp_tool_data = await mcp_client.get_all_tools()
        #     mcp_function_declarations = []
        #     for server_name, mcp_tools in mcp_tool_data.items():
        #         for tool in mcp_tools:
        #             cleaned_schema = self.clean_schema(tool.get('inputSchema', {}))
        #             mcp_tool = genai.types.FunctionDeclaration(
        #                 name=tool["name"],
        #                 description=f"[MCP:{server_name}] {tool.get('description', 'No description provided.')}",
        #                 parameters=cleaned_schema
        #             )
        #             mcp_function_declarations.append(mcp_tool)
            
        #     if mcp_function_declarations:
        #         tools.append(genai.types.Tool(function_declarations=mcp_function_declarations))
        # except Exception as e:
        #     print(f"⚠️ Could not load MCP tools: {e}")
        print('\033[92m=====tools=====\033[0m',tools)
        return tools
    
    async def chat_completion_with_tools(
        self,
        messages: List[Dict],
        local_tools: List[Dict]
    ):
        tools = await self.merge_tools(local_tools)
        config = genai.types.GenerateContentConfig(tools=tools)
        
        # Convert messages to prompt
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompt += "\n\nIf the user asks multiple questions or requests multiple actions, please call the appropriate tools for each task in a single response. When sending emails about information you need to fetch (like weather), include that information in the email body."

        response = self.client.models.generate_content(
            model=self.model, 
            contents=prompt,
            config=config
        )
        print('\033[92m=====response=====\033[0m',response)
        candidate = response.candidates[0]
        assistant_reply = response.text or ""
        
        # Check for function calls
        all_tool_calls = []
        if candidate.content.parts:
            for i, part in enumerate(candidate.content.parts):
                if part.function_call:
                    function_call = part.function_call
                    all_tool_calls.append({
                        "function": {
                            "name": function_call.name,
                            "arguments": json.dumps(dict(function_call.args))
                        },
                        "id": f"gemini_call_{i+1}"
                    })
        print('\033[92m=====all_tool_calls=====\033[0m',all_tool_calls)
        return all_tool_calls if all_tool_calls else None, assistant_reply