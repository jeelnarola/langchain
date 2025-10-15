tools_schema = [
    {
        "type": "tools",
        "tools": {
            "name": "pdf_tool",
            "description": (
                "- Always call pdf_tool with the user's question; never answer directly.\n"
                "- If a PDF exists, **call pdf_tool** with the user's question before any other processing.\n"
                "- Do not answer questions directly unless they are explicitly unrelated to PDFs.\n"
                "- call this tool when the user ask for personal details like the details you do not have\n"
            ),
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
            "name": "product_insert_tool",
            "description": "Insert a new product into the system with name, price, and optional category",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name"},
                    "price": {"type": "number", "description": "Product price"},
                    "category": {
                        "type": "string",
                        "description": "Optional product category",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional product description",
                    },
                },
                "required": ["name", "price"],
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
