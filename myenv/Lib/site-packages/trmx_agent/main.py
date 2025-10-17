"""
Main functionality for the chat agent.
"""

import sys
import socket
import requests
import importlib
import re  # Added for regex pattern matching
from typing import Optional, List, Dict, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

from .config import config
from .storage import ChatSession

console = Console()

# Try to import the Together AI model config if available
try:
    from airtrain.integrations.together.models_config import get_max_completion_tokens
    HAS_TOGETHER_CONFIG = True
except ImportError:
    HAS_TOGETHER_CONFIG = False

# Simple token estimator for fallback
def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in text using a simple heuristic."""
    # Average English word is ~4 characters, and average token is ~4 characters
    return len(text) // 4

def count_tokens_in_messages(messages: List[Dict[str, str]]) -> int:
    """Count tokens in a list of messages."""
    total_tokens = 0
    for message in messages:
        # Count tokens in the message content
        content = message.get("content", "")
        total_tokens += estimate_tokens(content)
        # Add a small overhead for the message format (role, etc.)
        total_tokens += 4
    # Add a small overhead for the message list format
    total_tokens += 10
    return total_tokens

def check_internet_connectivity() -> Tuple[bool, str]:
    """Check if internet is accessible.

    Returns:
        Tuple[bool, str]: (is_connected, error_message)
    """
    try:
        # Try to connect to Google's DNS server
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True, ""
    except OSError:
        # Try an alternative method using requests
        try:
            requests.get("https://www.google.com", timeout=3)
            return True, ""
        except requests.RequestException:
            msg = "Cannot connect to the internet. Please check your connection."
            return False, msg


class ChatAgent:
    """Chat agent that interfaces with AI providers via AirTrain."""

    def __init__(self, session_id: Optional[str] = None):
        """Initialize the chat agent with an optional session ID."""
        # Load or create a chat session
        if session_id:
            self.session = ChatSession.load(session_id)
            if not self.session:
                msg = (
                    f"[red]Session {session_id} not found. "
                    f"Creating a new session.[/red]"
                )
                console.print(msg)
                self.session = ChatSession()
        else:
            self.session = ChatSession()

        # Load the active provider and model
        self.provider = config.get_active_provider()
        self.model = config.get_active_model()
        
        # Option to show thinking content
        self.show_thinking = False
        
        # Update session with provider and model info if needed
        if not self.session.provider or not self.session.model:
            self.session.set_provider_model(self.provider, self.model)

        # Check for API key and handle setup if missing
        if not config.is_api_key_set:
            self._handle_missing_credentials()

        # Check if we have credentials now
        if not config.is_api_key_set:
            console.print("[red]Error: Could not set up API credentials.[/red]")
            console.print(f"Please try again or set {self.provider.upper()}_API_KEY manually.")
            sys.exit(1)

        # Initialize the provider-specific client and skill
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the provider-specific client and skill."""
        provider_module_path = config.get_provider_module_path(self.provider)
        if not provider_module_path:
            console.print(f"[red]Error: Provider '{self.provider}' is not supported.[/red]")
            sys.exit(1)

        try:
            # Import the provider's skill and credentials modules
            skill_module = importlib.import_module(f"{provider_module_path}.skills")
            creds_module = importlib.import_module(f"{provider_module_path}.credentials")

            # Determine class names based on provider
            if self.provider == "together":
                creds_class_name = "TogetherAICredentials"
                chat_skill_class_name = "TogetherAIChatSkill"
                input_class_name = "TogetherAIInput"
            elif self.provider == "openai":
                creds_class_name = "OpenAICredentials"
                chat_skill_class_name = "OpenAIChatSkill"
                input_class_name = "OpenAIInput"
            elif self.provider == "google":
                creds_class_name = "GeminiCredentials"
                chat_skill_class_name = "GeminiChatSkill"
                input_class_name = "GeminiInput"
            else:
                # Default pattern for other providers
                creds_class_name = f"{self.provider.capitalize()}Credentials"
                chat_skill_class_name = f"{self.provider.capitalize()}ChatSkill"
                input_class_name = f"{self.provider.capitalize()}Input"

            # Get the classes
            creds_class = getattr(creds_module, creds_class_name)
            chat_skill_class = getattr(skill_module, chat_skill_class_name)
            self.input_class = getattr(skill_module, input_class_name)

            # Get the API key for this provider
            api_key = config.get_provider_api_key(self.provider)

            # Initialize credentials
            credentials_kwargs = {f"{self.provider}_api_key": api_key}
            self.credentials = creds_class(**credentials_kwargs)

            # Initialize chat skill
            self.chat_skill = chat_skill_class(credentials=self.credentials)

        except (ImportError, AttributeError) as e:
            console.print(f"[red]Error initializing provider '{self.provider}': {str(e)}[/red]")
            sys.exit(1)

    def _handle_missing_credentials(self) -> None:
        """Handle missing credentials by prompting the user."""
        console.print(f"[yellow]Warning: {self.provider.capitalize()} API key not found![/yellow]")
        msg = "The API key was not found in environment variables or credentials file."
        console.print(msg)
        creds_path = config.credentials_dir / f"{self.provider}.json"
        console.print(f"Credentials should be in: {creds_path}")
        console.print()

        set_key = Confirm.ask(f"Would you like to set your {self.provider.capitalize()} API key now?")
        if set_key:
            api_key = Prompt.ask(f"Enter your {self.provider.capitalize()} API key", password=True)
            if api_key:
                if config.save_provider_credentials(self.provider, api_key):
                    console.print(f"[green]API key saved successfully.[/green]")
                else:
                    console.print(f"[red]Failed to save API key.[/red]")
            else:
                console.print("[yellow]No API key provided.[/yellow]")

    def chat(self) -> None:
        """Start an interactive chat session."""
        # Remove connectivity checks from here - we'll check only when making API calls

        console.print("[bold blue]Chat Session Started[/bold blue]")
        console.print(f"Session ID: {self.session.session_id}")
        console.print()
        console.print("[bold]AI Model Information:[/bold]")
        console.print(
            "[bold cyan]Provider:[/bold cyan] [cyan]{0}[/cyan]".format(
                self.provider.capitalize()
            )
        )
        console.print(
            "[bold cyan]Model:[/bold cyan] [cyan]{0}[/cyan]".format(self.model)
        )
        console.print()
        console.print("Type 'exit', 'quit', or 'q' to end the session.")
        console.print("For multi-line input, use one of these triggers:")
        console.print("  - /m, /multiline, /multi, /p, /paste (end with /end)")
        console.print("  - \"\"\" (end with \"\"\")")
        console.print("  - ''' (end with ''')")
        console.print()

        # Make sure thinking content is extracted for all assistant messages
        # This ensures backward compatibility with sessions created before this feature
        for message in self.session.messages:
            if message["role"] == "assistant" and "thinking" not in message:
                thinking_match = re.search(r"<think>(.*?)</think>", message["content"], re.DOTALL)
                if thinking_match:
                    thinking_content = thinking_match.group(1).strip()
                    message["thinking"] = thinking_content
                    # No need to save here as we're just enhancing the in-memory representation

        # Display existing messages if any
        if self.session.messages:
            console.print("[bold]Chat History:[/bold]")
            for message in self.session.messages:
                if message["role"] == "user":
                    console.print(f"[bold green]You:[/bold green] {message['content']}")
                else:
                    console.print("[bold purple]AI:[/bold purple]")
                    
                    # Display thinking content if available and show_thinking is enabled
                    if self.show_thinking and "thinking" in message:
                        console.print("[bold yellow]Model's Thinking:[/bold yellow]")
                        console.print(Markdown(message["thinking"]))
                        console.print("\n[bold purple]Final Response:[/bold purple]")
                        
                    # Display the message content (might need to strip thinking tags)
                    display_content = message["content"]
                    if self.show_thinking:
                        # Remove thinking tags from displayed content
                        display_content = re.sub(
                            r"<think>.*?</think>", 
                            "", 
                            display_content, 
                            flags=re.DOTALL
                        ).strip()
                    console.print(Markdown(display_content))
            console.print("\n[bold]Continuing conversation...[/bold]\n")

        # Interactive chat loop
        while True:
            try:
                # Get user input (potentially multi-line)
                user_input = self._get_user_input()
                
                if user_input is None:  # User canceled input
                    continue

                # Check for exit command
                if user_input.lower() in ["exit", "quit", "q"]:
                    console.print("[bold blue]Ending chat session...[/bold blue]")
                    break

                # Add user message to session
                self.session.add_message("user", user_input)

                # Format messages for the API
                messages = self._format_messages_for_api()
                system_prompt = "You are a helpful assistant."

                # Check internet connectivity only when about to make an API call
                internet_connected, internet_error = check_internet_connectivity()
                if not internet_connected:
                    console.print(f"[bold red]Error: {internet_error}[/bold red]")
                    continue  # Continue the loop to allow user to try again or quit

                # Calculate max_tokens based on provider and model
                max_tokens = 131072  # Default fallback value
                
                # Special handling for Together AI to avoid token limit errors
                if self.provider == "together":
                    # Get the model's max completion tokens from the config if available
                    model_max_tokens = 1024  # Conservative default
                    if HAS_TOGETHER_CONFIG:
                        try:
                            model_max_tokens = get_max_completion_tokens(self.model)
                        except Exception as e:
                            console.print(
                                f"[yellow]Warning: Could not get max tokens for model: {str(e)}[/yellow]"
                            )
                    
                    # Count tokens in the conversation
                    input_tokens = count_tokens_in_messages(messages)
                    
                    # Calculate available tokens (subtract input tokens and a safety margin)
                    available_tokens = model_max_tokens - input_tokens - 200
                    max_tokens = available_tokens
                    
                    console.print(
                        f"[dim]Using {max_tokens} max tokens for response[/dim]"
                    )

                # Prepare the input for the provider's skill
                input_kwargs = {
                    "user_input": user_input,
                    "system_prompt": system_prompt,
                    "conversation_history": messages[:-1],  # Exclude the last user message
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                }
                
                input_data = self.input_class(**input_kwargs)

                # Call the API
                console.print("[bold purple]AI:[/bold purple]")
                with console.status("[bold]Thinking...[/bold]"):
                    result = self.chat_skill.process(input_data)

                # Get AI response
                ai_response = result.response
                
                # Check for thinking tags if show_thinking is enabled
                if self.show_thinking:
                    # Extract thinking content if present
                    thinking_match = re.search(r"<think>(.*?)</think>", ai_response, re.DOTALL)
                    if thinking_match:
                        thinking_content = thinking_match.group(1).strip()
                        # Display thinking content
                        console.print("[bold yellow]Model's Thinking:[/bold yellow]")
                        console.print(Markdown(thinking_content))
                        console.print("\n[bold purple]Final Response:[/bold purple]")
                        
                        # Remove thinking content from final response for display
                        display_content = re.sub(
                            r"<think>.*?</think>", 
                            "", 
                            ai_response, 
                            flags=re.DOTALL
                        ).strip()
                        console.print(Markdown(display_content))
                    else:
                        # No thinking content found
                        console.print(Markdown(ai_response))
                else:
                    # show_thinking is disabled, just show the response without any thinking parts
                    display_content = re.sub(
                        r"<think>.*?</think>", 
                        "", 
                        ai_response, 
                        flags=re.DOTALL
                    ).strip()
                    console.print(Markdown(display_content))

                # Add AI message to session
                self.session.add_message("assistant", result.response)  # Store original response with thinking tags

            except KeyboardInterrupt:
                interrupt_msg = (
                    "\n[bold blue]Chat session interrupted. "
                    "Saving and exiting...[/bold blue]"
                )
                console.print(interrupt_msg)
                break
            except Exception as e:
                console.print(f"[bold red]Error: {str(e)}[/bold red]")
                continue

    def _get_user_input(self) -> Optional[str]:
        """Get user input, supporting multi-line input with various triggers."""
        # Get the first line of input
        first_line = console.input("[bold green]You:[/bold green] ")
        
        # Check for multi-line input triggers
        multiline_triggers = ["/m", "/multiline", "/multi", "/p", "/paste"]
        quote_triggers = ["\"\"\"", "'''"]
        
        # For command-based triggers
        if first_line in multiline_triggers:
            return self._collect_multiline_input("/end")
        
        # For quote-based triggers
        for trigger in quote_triggers:
            if first_line == trigger:
                return self._collect_multiline_input(trigger)
        
        # Regular single-line input
        return first_line
    
    def _collect_multiline_input(self, terminator: str) -> Optional[str]:
        """Collect multi-line input until the terminator is encountered."""
        console.print(
            f"[bold cyan]Multi-line input mode.[/bold cyan]"
            f" [bold cyan]End with '{terminator}' on a new line.[/bold cyan]"
        )
        lines = []
        
        try:
            while True:
                line = console.input()
                if line == terminator:
                    break
                lines.append(line)
                
            # Join the lines with newlines
            if not lines:  # Empty input
                console.print("[yellow]Empty input. Cancelled.[/yellow]")
                return None
                
            return "\n".join(lines)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Multi-line input cancelled.[/yellow]")
            return None

    def _format_messages_for_api(self) -> List[Dict[str, str]]:
        """Format the messages for the Together AI API."""
        # Filter out timestamp and other metadata
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.session.messages
        ]
