import json
import os
import inspect
import datetime
import requests
import sys
import smtplib
import xml.etree.ElementTree as ET
from typing import Callable, Dict
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI

from services.documentService import get_all_vector_paths
from services.productService import save_product_db

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from mcp_client import mcp_client, call_mcp_tool

# --- Tool Registry ---
TOOLS: Dict[str, Callable] = {}
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def get_embeddings():
    return OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)


def weather_tool(city: str) -> dict:
    """Get the current weather for a given city."""
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_params = {"name": city, "count": 1}
    geo_resp = requests.get(geo_url, params=geo_params)
    geo_data = geo_resp.json()
    if not geo_data.get("results"):
        return {"error": f"Location '{city}' not found"}

    lat = geo_data["results"][0]["latitude"]
    lon = geo_data["results"][0]["longitude"]
    today = datetime.date.today().strftime("%Y-%m-%d")

    weather_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,
        "timezone": "auto",
    }
    weather_resp = requests.get(weather_url, params=params)
    weather_data = weather_resp.json()
    current = weather_data.get("current_weather", {})
    temperature = current.get("temperature")
    print('\033[92m=====weather_tool=====\033[0m')
    return {
        "location": city,
        "lat": lat,
        "lon": lon,
        "date": today,
        "weather": current,
        "message": f"The current temperature in {city} is {temperature}°C.",
    }


def pdf_tool(query: str, db=None) -> str:
    if not db:
        from config.database import get_db
        db = next(get_db())
    
    vector_paths = get_all_vector_paths(db)
    if not vector_paths:
        return "No PDF documents available."

    retriever_docs = []
    for vector_path in vector_paths:
        store = Chroma(
            persist_directory=vector_path,
            embedding_function=get_embeddings(),
        )
        docs = store.similarity_search(query, k=3)
        retriever_docs.extend(docs)

    if not retriever_docs:
        return "No relevant information found in PDF."

    context = "\n\n".join([doc.page_content for doc in retriever_docs[:5]])
    
    extraction_prompt = f"""
You are an assistant that extracts concise, direct answers from PDF context.

PDF Context:
{context}

User Question:
{query}

Instruction:
- Provide the answer as plain text.
- If no answer is clear, respond "I don't know."
"""
    summary = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": extraction_prompt}],
        stream=False,
    )

    return summary.choices[0].message.content.strip()


def product_insert_tool(
    name: str, price: float, description: str, category: str = "general", **kwargs
) -> dict:
    """Insert a new product into the system."""
    product = {
        "name": name,
        "price": price,
        "category": category,
        "description": description,
        "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    save_product_db(product)
    
    return {
        "status": "success",
        "message": "Product inserted successfully",
        "product": product,
    }


def send_email_tool(to_email: str, subject: str, body: str, mode: str = "send"):
    """Send an email via SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"] = os.getenv("SMTP_USER")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT")))
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.sendmail(os.getenv("SMTP_USER"), to_email, msg.as_string())
        server.quit()

        return {"status": "success", "message": f"Email sent to {to_email}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def handle_tool_call(tool_call, db=None, context=None):
    """Executes a tool call and returns structured output."""
    if isinstance(tool_call, dict):
        tool_name = tool_call["function"]["name"]
        tool_args_raw = tool_call["function"]["arguments"]
        server_name = tool_call.get("server_name")
    else:
        tool_name = tool_call.function.name
        tool_args_raw = tool_call.function.arguments
        server_name = None

    if isinstance(tool_args_raw, str):
        try:
            tool_args = json.loads(tool_args_raw) if tool_args_raw else {}
        except json.JSONDecodeError:
            tool_args = {}
    elif isinstance(tool_args_raw, dict):
        tool_args = tool_args_raw
    else:
        tool_args = {}

    # Check if this is an MCP tool call
    if server_name:
        try:
            # Set chat_id from context if available
            print(f"Debug: context={context}, tool_name={tool_name}")
            if context and "chat_id" in context and tool_name == "send_message":
                print(f"🔧 Replacing chat_id {tool_args.get('chat_id')} with {context['chat_id']}")
                tool_args["chat_id"] = context["chat_id"]
            else:
                print("❌ No chat_id replacement - missing context or not send_message")
            
            result = await call_mcp_tool(server_name, tool_name, tool_args)
            # Extract simple message from MCP result
            if isinstance(result, list) and result:
                message = result[0].text if hasattr(result[0], 'text') else str(result[0])
                print('\033[92m=====message=====\033[0m',message)
            else:
                message = str(result) if result else "MCP tool executed successfully"
            
            return {
                "status": "success",
                "tool": tool_name,
                "result": result,
                "message": message,
            }
        except Exception as e:
            return {
                "status": "error",
                "tool": tool_name,
                "result": None,
                "message": f"MCP tool execution failed: {str(e)}",
            }

    # Handle local tools
    tool_fn = {
        "weather_tool": weather_tool,
        "pdf_tool": pdf_tool,
        "send_email_tool": send_email_tool,
        "product_insert_tool": product_insert_tool,
    }.get(tool_name)

    if not tool_fn:
        return {
            "status": "error",
            "tool": tool_name,
            "message": f"Unknown tool {tool_name}",
        }

    try:
        # Add db parameter for tools that need it
        if tool_name == "pdf_tool" and db:
            tool_args["db"] = db

        if inspect.iscoroutinefunction(tool_fn):
            tool_output = await tool_fn(**tool_args)
        else:
            tool_output = tool_fn(**tool_args)

        if isinstance(tool_output, dict):
            tool_message = tool_output.get("message", json.dumps(tool_output))
        else:
            tool_message = str(tool_output)

        return {
            "status": "success",
            "tool": tool_name,
            "result": tool_output,
            "message": tool_message,
        }

    except Exception as e:
        return {
            "status": "error",
            "tool": tool_name,
            "result": None,
            "message": f"Tool execution failed: {str(e)}",
        }


def parse_use_mcp_tool(xml_call: str) -> dict:
    """Parse <use_mcp_tool> XML into a dict."""
    xml_call = xml_call.strip()
    if not xml_call.startswith("<use_mcp_tool>") or not xml_call.endswith("</use_mcp_tool>"):
        return {}

    try:
        root = ET.fromstring(xml_call)
    except ET.ParseError:
        return {}
    
    server_name = root.findtext("server_name")
    tool_name = root.findtext("tool_name")
    args_elem = root.find("arguments")
    args_text = args_elem.text if args_elem is not None else "{}"

    args_text = args_text.strip()
    if args_text.startswith("<![CDATA[") and args_text.endswith("]]>"):
        args_text = args_text[9:-3]

    args_text = args_text.replace("{{", "{").replace("}}", "}")
    try:
        tool_args = json.loads(args_text)
    except json.JSONDecodeError:
        tool_args = {}

    return {
        "function": {"name": tool_name, "arguments": tool_args},
        "server_name": server_name,
    }


async def get_all_mcp_tools():
    """Get all available tools from all MCP servers"""
    try:
        return await mcp_client.get_all_tools()
    except Exception as e:
        print(f"Error getting MCP tools: {e}")
        return {}