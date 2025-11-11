# openai_client.py
from openai import OpenAI

class OpenAIClient:
    """
    Wrapper around the OpenAI SDK to handle LLM calls, tool execution,
    and error-safe completions.
    """

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    async def chat_completion(
        self,
        messages,
        tools=None,
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=1000,
    ):
        """Handles a single chat completion call."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response
        except Exception as e:
            print(f"❌ LLM API Error: {e}")
            return None
