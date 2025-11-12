tools_schema = [
    {
        "type": "function",
        "function": {
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
        "type": "function",
        "function": {
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
        "type": "function",
        "function": {
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
