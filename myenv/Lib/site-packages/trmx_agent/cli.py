"""
Command-line interface for the chat agent.
"""

from typing import Optional, Tuple
import importlib.metadata
import sys
import subprocess
import requests

import typer
from rich.console import Console
from rich.table import Table
from packaging import version

from .config import config
from .main import ChatAgent
from .storage import ChatSession

app = typer.Typer(help="A terminal chat interface for interacting with multiple AI models.")
console = Console()

# Define command names to prioritize over session IDs
COMMAND_NAMES = ["list", "info", "chat"]


def check_for_updates() -> Tuple[bool, str, str]:
    """Check if a newer version of the package is available on PyPI.
    
    Returns:
        Tuple[bool, str, str]: (update_available, current_version, latest_version)
    """
    try:
        current_version = importlib.metadata.version("modelcontextprotocol")
    except importlib.metadata.PackageNotFoundError:
        return False, "unknown", "unknown"
    
    try:
        # Fetch the latest version from PyPI
        response = requests.get(
            "https://pypi.org/pypi/modelcontextprotocol/json", 
            timeout=5
        )
        if response.status_code != 200:
            return False, current_version, "unknown"
        
        data = response.json()
        latest_version = data["info"]["version"]
        
        # Compare versions
        return (
            version.parse(latest_version) > version.parse(current_version),
            current_version,
            latest_version
        )
    except (requests.RequestException, KeyError, ValueError):
        # Handle any errors gracefully
        return False, current_version, "unknown"


def update_package() -> bool:
    """Update the package using pip.
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    update_available, current_version, latest_version = check_for_updates()
    
    if not update_available or latest_version == "unknown":
        console.print(
            f"[yellow]You already have the latest version: {current_version}[/yellow]"
        )
        return False
    
    msg = f"[green]Updating mcp from version {current_version} to {latest_version}...[/green]"
    console.print(msg)
    
    try:
        # Run pip to update the package
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "modelcontextprotocol"],
            capture_output=True,
            text=True,
            check=True
        )
        
        console.print("[green]Update successful![/green]")
        if result.stdout.strip():
            console.print(f"[dim]{result.stdout.strip()}[/dim]")
        return True
    except subprocess.CalledProcessError as e:
        console.print("[red]Update failed:[/red]")
        if e.stderr.strip():
            console.print(f"[red]{e.stderr.strip()}[/red]")
        return False


def find_session_by_partial_id(partial_id: str) -> Optional[str]:
    """Find a session by partial ID match (prefix)."""
    if not partial_id:
        return None

    sessions = ChatSession.list_sessions()
    for session in sessions:
        if session["session_id"].startswith(partial_id):
            return session["session_id"]
    return None


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Argument(
        None, help="Session ID to continue (can be partial)"
    ),
    list_sessions_flag: bool = typer.Option(
        False, "--list", "-l", help="List all available chat sessions."
    ),
    info_flag: bool = typer.Option(
        False, "--info", "-i", help="Show information about the chat storage location."
    ),
    chat_flag: bool = typer.Option(
        False, "--chat", help="Start a chat session with the AI."
    ),
    continue_session: Optional[str] = typer.Option(
        None,
        "--continue",
        "-c",
        help="Continue an existing chat session (can be partial ID).",
    ),
    delete_session: Optional[int] = typer.Option(
        None,
        "--delete",
        help="Delete a chat session by its number in the list.",
    ),
    help_flag: bool = typer.Option(
        False, "--help", "-h", help="Show this message and exit.", is_eager=True
    ),
    version_flag: bool = typer.Option(
        False, "--version", "-v", help="Show the version and exit.", is_eager=True
    ),
    update_flag: bool = typer.Option(
        False, "--update", help="Update mcp to the latest version.", is_eager=True
    ),
    add_config: bool = typer.Option(
        False, "--add", help="Add a new provider/model configuration."
    ),
    show_thinking: bool = typer.Option(
        False, 
        "--show-thinking", "-s", "-st", 
        help="Show thinking process for models that use <think> tags."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Specify the provider to use (e.g., openai, anthropic, together)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Specify the model to use."
    ),
    list_providers: bool = typer.Option(
        False, "--list-providers", "-lp", help="List available providers."
    ),
    list_models: bool = typer.Option(
        False, "--list-models", "-lm", help="List available models for the current or specified provider."
    ),
    set_timestyle: Optional[str] = typer.Option(
        None, 
        "--set-timestyle", 
        help="Set the time display style (iso, human, or relative)."
    ),
):
    """Run the chat agent CLI."""
    # Check for update flag
    if update_flag:
        update_package()
        return
        
    # Show version if requested
    if version_flag:
        try:
            version = importlib.metadata.version("modelcontextprotocol")
            console.print(f"mcp version: [cyan]{version}[/cyan]")
            
            # Check if a newer version is available
            update_available, _, latest_version = check_for_updates()
            if update_available:
                console.print(
                    f"[yellow]A new version ({latest_version}) is available![/yellow]"
                )
                console.print("[yellow]Run 'mcp --update' to upgrade.[/yellow]")
        except importlib.metadata.PackageNotFoundError:
            console.print("[yellow]Package version information not available[/yellow]")
        return

    # Show help if explicitly requested
    if help_flag:
        console.print(ctx.get_help())
        return

    # Set time style if requested
    if set_timestyle:
        if set_timestyle not in ["iso", "human", "relative"]:
            console.print(f"[red]Invalid time style: {set_timestyle}[/red]")
            console.print("Valid options are: iso, human, relative")
            return
            
        if config.set_time_style(set_timestyle):
            console.print(f"[green]Time style set to: {set_timestyle}[/green]")
        else:
            console.print("[red]Failed to save time style setting[/red]")
        return

    # List available providers
    if list_providers:
        config.list_providers()
        return

    # List available models for a provider
    if list_models:
        config.list_models(provider)
        return

    # Add a new provider/model configuration
    if add_config:
        if not provider or not model:
            console.print("[red]Error: Both --provider and --model must be specified when using --add[/red]")
            return
        success = config.add_provider_model_config(provider, model)
        if success:
            console.print(f"[green]Successfully configured {provider}/{model}[/green]")
            console.print("This configuration will be used for new chat sessions.")
        return

    # Check if provider/model are specified without --add
    if provider or model:
        config.set_active_provider_model(provider, model)
        if chat_flag or continue_session or session_id is None:
            console.print(f"[green]Using provider/model: {config.get_active_provider()}/{config.get_active_model()}[/green]")
            # Continue to chat with the specified provider/model
        else:
            return

    # Check if any of the option flags are set
    if list_sessions_flag:
        show_sessions_list()
        return

    if info_flag:
        show_storage_info()
        return

    if delete_session is not None:
        delete_session_by_number(delete_session)
        return

    if chat_flag or continue_session:
        # If continue_session is provided, try to find a match with a partial ID
        if continue_session:
            full_id = find_session_by_partial_id(continue_session)
            if full_id:
                continue_session = full_id
                console.print(f"Continuing session: [cyan]{full_id}[/cyan]")
            else:
                console.print(f"[red]Session '{continue_session}' not found[/red]")
                console.print("Use 'mcp --list' to see available sessions.")
                return

        _start_chat(session_id=continue_session, show_thinking=show_thinking)
        return

    # If no options are set, check if a session ID is provided
    if session_id:
        # Try to find a session with a matching prefix
        full_session_id = find_session_by_partial_id(session_id)
        if full_session_id:
            console.print(f"Continuing session: [cyan]{full_session_id}[/cyan]")
            # Don't call the chat function directly to avoid Typer's parameter handling
            _start_chat(session_id=full_session_id, show_thinking=show_thinking)
        else:
            console.print(f"[red]Session '{session_id}' not found[/red]")
            console.print("Use 'mcp --list' to see available sessions.")
    else:
        # Start a new chat session by default instead of showing help
        _start_chat(session_id=None, show_thinking=show_thinking)


def _start_chat(session_id: Optional[str] = None, show_thinking: bool = False):
    """Start a chat session without Typer's parameter handling."""
    agent = ChatAgent(session_id=session_id)
    agent.show_thinking = show_thinking
    agent.chat()


def show_sessions_list():
    """List all available chat sessions."""
    sessions = ChatSession.list_sessions()

    if not sessions:
        console.print("[yellow]No chat sessions found.[/yellow]")
        return

    table = Table(title="Available Chat Sessions")
    table.add_column("#", style="white")
    table.add_column("Title", style="yellow")
    table.add_column("Session ID", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Messages", style="blue")
    table.add_column("Provider", style="magenta")
    table.add_column("Model", style="purple")
    table.add_column("Preview", style="dim white")

    for i, session in enumerate(sessions, 1):
        # Truncate model name if too long
        model_name = session.get("model", "Unknown")
        if model_name and len(model_name) > 15:
            model_parts = model_name.split('/')
            if len(model_parts) > 1:
                model_name = f"{model_parts[-2][:5]}/../{model_parts[-1][:10]}"
            else:
                model_name = model_name[:15] + "..."
                
        # Format provider name with capitalization
        provider_name = session.get("provider", "Unknown")
        if provider_name != "Unknown":
            provider_name = provider_name.capitalize()
                
        # Add row
        table.add_row(
            str(i),
            session.get("title", "New Chat"),
            session["session_id"][:12] + "...",  # Truncate session ID 
            session.get("formatted_time", session["created_at"]),
            str(session["message_count"]),
            provider_name,
            model_name,
            session.get("preview", "No preview available"),
        )

    console.print(table)


def delete_session_by_number(session_number: int):
    """Delete a chat session by its number in the list."""
    sessions = ChatSession.list_sessions()

    if not sessions:
        console.print("[yellow]No chat sessions found to delete.[/yellow]")
        return

    if session_number < 1 or session_number > len(sessions):
        console.print(f"[red]Invalid session number: {session_number}[/red]")
        console.print(f"Please choose a number between 1 and {len(sessions)}")
        return

    # Get the session ID for the given number
    session_id = sessions[session_number - 1]["session_id"]

    # Delete the session
    if ChatSession.delete_session(session_id):
        sid = session_id[:20] + "..." if len(session_id) > 23 else session_id
        msg = f"[green]Successfully deleted session {session_number}: {sid}[/green]"
        console.print(msg)
    else:
        sid = session_id[:20] + "..." if len(session_id) > 23 else session_id
        msg = f"[red]Failed to delete session {session_number}: {sid}[/red]"
        console.print(msg)


def show_storage_info():
    """Show information about the chat storage location."""
    console.print("Chat history storage location:")
    console.print(f"[green]{config.storage_dir}[/green]")
    console.print(f"Credentials location: [green]{config.credentials_dir}[/green]")
    console.print(f"Configuration location: [green]{config.config_dir}[/green]")

    # Check if the directory exists
    if config.storage_dir.exists():
        console.print("Chat storage directory exists: [green]Yes[/green]")
        sessions = ChatSession.list_sessions()
        console.print(f"Number of sessions: [blue]{len(sessions)}[/blue]")
    else:
        console.print("Chat storage directory exists: [red]No[/red]")
        console.print(
            "[yellow]The directory will be created when you start a chat.[/yellow]"
        )


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()