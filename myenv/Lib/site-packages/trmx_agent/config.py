"""
Configuration management for the chat agent.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from loguru import logger

# Import airtrain's ListModelsSkillFactory
try:
    from airtrain.integrations import (
        ListModelsSkillFactory,
        GenericListModelsInput
    )
    HAS_LIST_MODELS_FACTORY = True
except ImportError:
    HAS_LIST_MODELS_FACTORY = False

# Load environment variables from .env file if it exists
load_dotenv()

console = Console()

# Default configuration
DEFAULT_STORAGE_DIR = Path.home() / ".trmx" / "messages"
DEFAULT_CREDENTIALS_DIR = Path.home() / ".trmx" / "credentials"
DEFAULT_TOGETHER_CREDENTIALS_FILE = DEFAULT_CREDENTIALS_DIR / "togetherai.json"
DEFAULT_CONFIG_DIR = Path.home() / ".trmx" / "config"
DEFAULT_PROVIDERS_CONFIG_FILE = DEFAULT_CONFIG_DIR / "providers.json"
DEFAULT_USER_SETTINGS_FILE = DEFAULT_CONFIG_DIR / "settings.json"

# Default settings
DEFAULT_TIME_STYLE = "iso"  # Options: "iso", "human", "relative"

# List of supported providers and their package paths
PROVIDERS = {
    "together": "airtrain.integrations.together",
    "openai": "airtrain.integrations.openai",
    "anthropic": "airtrain.integrations.anthropic",
    "groq": "airtrain.integrations.groq",
    "fireworks": "airtrain.integrations.fireworks",
    "cerebras": "airtrain.integrations.cerebras",
    "google": "airtrain.integrations.google",
}

# Default provider and model configuration
DEFAULT_PROVIDER = "together"
DEFAULT_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# Default models for each provider
DEFAULT_MODELS = {
    "together": [
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "meta-llama/Llama-2-70b-chat-hf",
        "togethercomputer/Llama-2-7B-32K-Instruct"
    ],
    "openai": [
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo"
    ],
    "anthropic": [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307"
    ],
    "groq": [
        "llama-3-70b-8192",
        "mixtral-8x7b-32768",
        "gemma-7b-it"
    ],
    "fireworks": [
        "fireworks/deepseek-r1", 
        "fireworks/llama-v3-70b",
        "fireworks/mixtral-8x7b-instruct"
    ],
    "cerebras": [
        "cerebras/Cerebras-GPT-13B-v0.1",
        "cerebras/Cerebras-GPT-111M-v0.9",
        "cerebras/Cerebras-GPT-590M-v0.7"
    ],
    "google": [
        "gemini-pro",
        "gemini-ultra",
        "gemini-flash"
    ]
}


class Config:
    """Configuration for the chat agent."""

    def __init__(self):
        """Initialize configuration with values from environment variables."""
        # Get storage directory from environment or use default
        storage_base = os.getenv("TRMX_DIR")
        if storage_base:
            self.storage_dir = Path(storage_base) / "messages"
            self.credentials_dir = Path(storage_base) / "credentials"
            self.config_dir = Path(storage_base) / "config"
        else:
            self.storage_dir = DEFAULT_STORAGE_DIR
            self.credentials_dir = DEFAULT_CREDENTIALS_DIR
            self.config_dir = DEFAULT_CONFIG_DIR

        # Ensure directories exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # User settings
        self.settings_file = self.config_dir / "settings.json"
        self.settings = self._load_settings()

        # Load provider configuration
        self.provider_config = self._load_provider_config()
        
        # Set active provider and model (from config or defaults)
        self.active_provider = self.provider_config.get(
            "active_provider", DEFAULT_PROVIDER
        )
        self.active_model = self.provider_config.get("active_model", DEFAULT_MODEL)

        # Initialize credentials
        self._initialize_credentials()

    def _initialize_credentials(self) -> None:
        """Initialize credentials for the active provider."""
        # The actual API key will be loaded in the main.py file when creating the credentials object
        # Here we just ensure we have a valid configuration
        self.provider_credentials = {}
        
        # Load Together AI credentials for backward compatibility
        if not self.provider_config.get("providers", {}).get("together", {}).get("api_key"):
            together_api_key = os.getenv("TOGETHER_API_KEY")
            if not together_api_key:
                together_api_key = self._load_together_credentials()
            
            if together_api_key:
                # Make sure we have a together entry in the providers
                if "providers" not in self.provider_config:
                    self.provider_config["providers"] = {}
                if "together" not in self.provider_config["providers"]:
                    self.provider_config["providers"]["together"] = {}
                
                self.provider_config["providers"]["together"]["api_key"] = together_api_key
                self._save_provider_config()

    def _load_provider_config(self) -> Dict[str, Any]:
        """Load provider configuration from file."""
        config_file = self.config_dir / "providers.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._create_default_provider_config()
        return self._create_default_provider_config()

    def _create_default_provider_config(self) -> Dict[str, Any]:
        """Create default provider configuration."""
        config = {
            "active_provider": DEFAULT_PROVIDER,
            "active_model": DEFAULT_MODEL,
            "providers": {}
        }
        
        # Save the default config
        self._save_provider_config(config)
        return config

    def _save_provider_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Save provider configuration to file."""
        if config is None:
            config = self.provider_config
            
        try:
            config_file = self.config_dir / "providers.json"
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            return True
        except IOError:
            return False

    def _load_together_credentials(self) -> str:
        """Load Together AI credentials from file (backward compatibility)."""
        # First try the new location
        creds_file = self.credentials_dir / "togetherai.json"
        if creds_file.exists():
            try:
                with open(creds_file, "r") as f:
                    creds = json.load(f)
                return creds.get("api_key", "")
            except (json.JSONDecodeError, IOError):
                pass  # Continue to legacy check if there's an error
                
        # Try the legacy location for backward compatibility
        if DEFAULT_TOGETHER_CREDENTIALS_FILE.exists():
            try:
                with open(DEFAULT_TOGETHER_CREDENTIALS_FILE, "r") as f:
                    creds = json.load(f)
                # If found in legacy location, save to new location
                api_key = creds.get("api_key", "")
                if api_key:
                    self.save_provider_credentials("together", api_key)
                return api_key
            except (json.JSONDecodeError, IOError):
                pass
                
        return ""

    def save_provider_credentials(self, provider: str, api_key: str) -> bool:
        """Save provider credentials to file."""
        try:
            # Ensure directories exist
            self.credentials_dir.mkdir(parents=True, exist_ok=True)

            # Save credentials to provider-specific file
            creds_file = self.credentials_dir / f"{provider}.json"
            with open(creds_file, "w") as f:
                json.dump({"api_key": api_key}, f, indent=2)

            # Update provider config
            if "providers" not in self.provider_config:
                self.provider_config["providers"] = {}
            if provider not in self.provider_config["providers"]:
                self.provider_config["providers"][provider] = {}
            
            self.provider_config["providers"][provider]["api_key"] = api_key
            self._save_provider_config()
            
            return True
        except IOError:
            return False

    def get_provider_api_key(self, provider: str) -> str:
        """Get API key for a specific provider."""
        # Check provider config first
        provider_info = self.provider_config.get("providers", {}).get(provider, {})
        if provider_info and "api_key" in provider_info:
            return provider_info["api_key"]
            
        # Check environment variables
        env_var = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var)
        if api_key:
            return api_key
            
        # Check provider-specific credential file
        creds_file = self.credentials_dir / f"{provider}.json"
        if creds_file.exists():
            try:
                with open(creds_file, "r") as f:
                    creds = json.load(f)
                return creds.get("api_key", "")
            except (json.JSONDecodeError, IOError):
                return ""
                
        return ""

    def add_provider_model_config(self, provider: str, model: str) -> bool:
        """Add or update a provider/model configuration."""
        # Check if provider is supported
        if provider not in PROVIDERS:
            console.print(f"[red]Error: Provider '{provider}' is not supported.[/red]")
            self.list_providers()
            return False
            
        # If provider exists but API key isn't set, prompt for it
        api_key = self.get_provider_api_key(provider)
        if not api_key:
            console.print(f"[yellow]No API key found for {provider}.[/yellow]")
            set_key = Confirm.ask(f"Would you like to set your {provider} API key now?")
            if set_key:
                api_key = Prompt.ask(f"Enter your {provider} API key", password=True)
                if api_key:
                    self.save_provider_credentials(provider, api_key)
                else:
                    console.print("[yellow]No API key provided.[/yellow]")
                    return False
            else:
                return False
                
        # Update the active provider and model
        self.active_provider = provider
        self.active_model = model
        
        # Update the config
        self.provider_config["active_provider"] = provider
        self.provider_config["active_model"] = model
        
        # Make sure model is in the models list for this provider
        if "providers" not in self.provider_config:
            self.provider_config["providers"] = {}
        if provider not in self.provider_config["providers"]:
            self.provider_config["providers"][provider] = {}
        if "models" not in self.provider_config["providers"][provider]:
            self.provider_config["providers"][provider]["models"] = []
            
        models = self.provider_config["providers"][provider]["models"]
        if model not in models:
            models.append(model)
            
        # Save the updated config
        return self._save_provider_config()

    def set_active_provider_model(self, provider: Optional[str] = None, model: Optional[str] = None) -> bool:
        """Set the active provider and/or model."""
        # If both are None, just return the current settings
        if provider is None and model is None:
            return True
            
        # Check provider
        if provider is not None:
            if provider not in PROVIDERS:
                console.print(f"[red]Error: Provider '{provider}' is not supported.[/red]")
                self.list_providers()
                return False
                
            # Check if provider has API key
            api_key = self.get_provider_api_key(provider)
            if not api_key:
                console.print(f"[yellow]Warning: No API key found for {provider}.[/yellow]")
                console.print(
                    f"Use 'trmx --add --provider {provider} --model <model>' to configure."
                )
                return False
                
            self.active_provider = provider
            self.provider_config["active_provider"] = provider
            
            # If no model specified, use the default for this provider
            if model is None:
                provider_models = self.get_models_for_provider(provider)
                if provider_models:
                    model = provider_models[0]  # Use first model as default
                    
        # Check model
        if model is not None:
            # Validate model if provider is set
            if provider is not None:
                provider_models = self.get_models_for_provider(provider)
                
                # If custom model not in default list, just accept it (could be new model)
                # But warn the user if we have a default list
                if provider_models and model not in provider_models:
                    console.print(f"[yellow]Warning: Model '{model}' is not in the default list for {provider}.[/yellow]")
                    console.print("This may still work if the model exists.")
            
            self.active_model = model
            self.provider_config["active_model"] = model
            
        # Save the updated config
        return self._save_provider_config()

    def get_active_provider(self) -> str:
        """Get the active provider."""
        return self.active_provider

    def get_active_model(self) -> str:
        """Get the active model."""
        return self.active_model

    def list_providers(self) -> None:
        """List available providers."""
        table = Table(title="Available Providers")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Default Model", style="yellow")
        
        for provider in PROVIDERS:
            # Check if provider has an API key
            api_key = self.get_provider_api_key(provider)
            status = "[green]✓ Configured[/green]" if api_key else "[red]✗ Not configured[/red]"
            
            # Get default model for this provider
            default_model = self.get_default_model_for_provider(provider)
            
            # Mark active provider
            provider_display = f"[bold]{provider}[/bold]" if provider == self.active_provider else provider
            
            table.add_row(provider_display, status, default_model)
            
        console.print(table)

    def list_models(self, provider: str = None) -> None:
        """List available models for a provider, or all if none specified"""
        if provider:
            providers = [provider]
        else:
            providers = list(PROVIDERS.keys())
        
        for provider in providers:
            try:
                # Try to get models with ListModelsSkillFactory first
                if HAS_LIST_MODELS_FACTORY:
                    try:
                        models = self._get_models_with_factory(provider)
                        if models:
                            self.display_models_table(provider, models)
                            continue
                    except Exception as e:
                        logger.warning(f"Error when displaying models with factory: {e}")
                        console.print(f"Factory error: {str(e)}")
                
                # Fall back to default model list
                console.print(f"Falling back to default model list.")
                models = self.get_models_for_provider(provider)
                
                # Create table
                table = Table(title=f"Available Models \nfor {provider}")
                table.add_column("Model", style="bold")
                table.add_column("Status")
                
                for model in models:
                    table.add_row(model, "")
                
                console.print(table)
                
            except Exception as e:
                console.print(f"[bold red]Error listing models for {provider}: {str(e)}[/bold red]")

    def _get_models_with_factory(self, provider: str) -> Optional[List[Dict[str, Any]]]:
        """Uses ListModelsSkillFactory to list models for a provider"""
        try:
            logger.info(f"Trying to fetch models for {provider} using ListModelsSkillFactory")
            
            # Get the factory
            factory = ListModelsSkillFactory()
            
            # Check if provider is supported
            supported_providers = factory.get_supported_providers()
            if provider.lower() not in [p.lower() for p in supported_providers]:
                logger.warning(f"Provider {provider} not supported by ListModelsSkillFactory")
                logger.info(f"Supported providers: {supported_providers}")
                return None
            
            # Get the skill for this provider
            skill = factory.get_skill(provider)
            logger.info(f"Got skill for provider {provider}")
            
            # Handle Fireworks special case for account_id
            if provider.lower() == "fireworks":
                # Use our enhanced approach from the scripts
                try:
                    from airtrain.integrations.fireworks.list_models import (
                        FireworksListModelsInput, 
                        FireworksListModelsSkill
                    )
                    
                    # List of Fireworks accounts to check
                    fireworks_accounts = ["fireworks", "perplexity", "sentientfoundation"]
                    
                    # Get account_id from environment if set
                    env_account = os.environ.get("FIREWORKS_ACCOUNT_ID")
                    if env_account:
                        # If set in environment, use it as the first account
                        if env_account not in fireworks_accounts:
                            fireworks_accounts.insert(0, env_account)
                        else:
                            # Move it to the front of the list
                            fireworks_accounts.remove(env_account)
                            fireworks_accounts.insert(0, env_account)
                    
                    # Store all models from all accounts
                    all_models_info = []
                    
                    # Try each account
                    for account_id in fireworks_accounts:
                        try:
                            logger.info(f"Using Fireworks account_id: {account_id}")
                            fireworks_skill = FireworksListModelsSkill(skill.credentials)
                            fireworks_input = FireworksListModelsInput(account_id=account_id)
                            result = fireworks_skill.process(fireworks_input)
                            logger.info(f"Successfully got Fireworks models for account: {account_id}")
                            
                            # Extract models in a standardized format
                            if hasattr(result, 'models') and result.models:
                                for model in result.models:
                                    if isinstance(model, dict):
                                        model_id = model.get("id", "") or model.get("model", "")
                                        # For Fireworks, extract account from model name if available
                                        model_account = account_id
                                        all_models_info.append({
                                            "model": model_id,
                                            "display_name": model.get("display_name", model_id),
                                            "status": model.get("status", ""),
                                            "account": model_account
                                        })
                                    else:
                                        # Handle FireworksModel object with attributes
                                        full_name = getattr(model, "name", "")
                                        
                                        # Extract account from full model name if it contains "accounts/"
                                        model_account = account_id
                                        if "accounts/" in full_name:
                                            # Format is typically "accounts/{account_name}/models/{model_name}"
                                            parts = full_name.split("/")
                                            if len(parts) >= 4 and parts[0] == "accounts":
                                                model_account = parts[1]
                                                model_id = parts[-1]  # Use the last part as model ID
                                            else:
                                                model_id = full_name.split("/")[-1]
                                        else:
                                            model_id = full_name.split("/")[-1]
                                            
                                        status = ""
                                        if hasattr(model, "state"):
                                            status = getattr(model, "state", "")
                                        
                                        all_models_info.append({
                                            "model": model_id,
                                            "display_name": model_id,
                                            "status": status,
                                            "account": model_account
                                        })
                        except Exception as e:
                            logger.warning(f"Error fetching models for Fireworks account {account_id}: {str(e)}")
                    
                    # If we got any models, return them
                    if all_models_info:
                        return all_models_info
                    
                    # Fallback to default models for Fireworks
                    logger.info("Falling back to default Fireworks models")
                    models_info = []
                    default_models = [
                        "llama-v3-70b-instruct", 
                        "firefunction-v1",
                        "deepseek-r1"
                    ]
                    for model in default_models:
                        models_info.append({
                            "model": model,
                            "display_name": model,
                            "status": "",
                            "account": "fireworks"
                        })
                    return models_info
                except Exception as e:
                    logger.warning(f"Error with direct Fireworks skill: {str(e)}")
                    
                    # Fallback to default models for Fireworks
                    logger.info("Falling back to default Fireworks models")
                    models_info = []
                    default_models = [
                        "llama-v3-70b-instruct", 
                        "firefunction-v1",
                        "deepseek-r1"
                    ]
                    for model in default_models:
                        models_info.append({
                            "model": model,
                            "display_name": model,
                            "status": "",
                            "account": "fireworks"
                        })
                    return models_info
            else:
                # For other providers, use the standard approach
                # Create input data for the skill
                input_data = GenericListModelsInput(api_models_only=False)
                # Process and get models
                result = skill.process(input_data)
            
            # Extract models from the result
            if hasattr(result, 'models'):
                # Standard format with 'models' attribute (Fireworks)
                models_info = []
                for model in result.models:
                    if isinstance(model, dict):
                        # If it's already a dict, use it directly
                        model_id = model.get("id", "") or model.get("name", "") or model.get("display_name", "")
                        model_info = {
                            "model": model_id,
                            "display_name": model.get("display_name", model_id),
                            "status": model.get("status", "")
                        }
                    else:
                        # Try to extract model info from object attributes
                        if hasattr(model, 'id'):
                            model_id = model.id
                        elif hasattr(model, 'name'):
                            model_id = model.name
                        else:
                            model_id = str(model)
                        
                        model_info = {
                            "model": model_id,
                            "display_name": getattr(model, "display_name", model_id),
                            "status": getattr(model, "status", "") or getattr(model, "state", "")
                        }
                    models_info.append(model_info)
                return models_info
            # Handle Together AI format with 'data' attribute
            elif hasattr(result, 'data'):
                models_info = []
                for model in result.data:
                    if isinstance(model, dict):
                        model_id = model.get("id", "")
                        model_info = {
                            "model": model_id,
                            "display_name": model.get("name", model_id),
                            "status": ""
                        }
                    else:
                        model_id = getattr(model, "id", str(model))
                        model_info = {
                            "model": model_id,
                            "display_name": getattr(model, "name", model_id),
                            "status": ""
                        }
                    models_info.append(model_info)
                return models_info
            else:
                logger.warning(f"Unexpected result format from {provider} skill")
                return None
            
        except Exception as e:
            logger.warning(f"Could not fetch models using ListModelsSkillFactory: {str(e)}")
            return None

    def get_models_for_provider(self, provider: str) -> List[str]:
        """Get available models for a provider."""
        # First check if we have custom models configured
        provider_info = self.provider_config.get("providers", {}).get(provider, {})
        if provider_info and "models" in provider_info:
            return provider_info["models"]
        
        # Try to get models using the factory
        if HAS_LIST_MODELS_FACTORY:
            try:
                models_list = self._get_models_with_factory(provider)
                return [model.get("id", "") for model in models_list if model.get("id")]
            except Exception:
                # Silently fall back to default models on error
                pass
            
        # Fall back to default models
        return DEFAULT_MODELS.get(provider, [])

    def get_default_model_for_provider(self, provider: str) -> str:
        """Get the default model for a provider."""
        models = self.get_models_for_provider(provider)
        return models[0] if models else "None available"

    @property
    def is_api_key_set(self) -> bool:
        """Check if the API key is set for the active provider."""
        return bool(self.get_provider_api_key(self.active_provider))

    def get_provider_module_path(self, provider: str) -> Optional[str]:
        """Get the module path for a provider."""
        return PROVIDERS.get(provider)

    def get_sessions_list(self) -> list[Path]:
        """Return a list of all session files in the storage directory."""
        return self.storage_dir.glob("*.json")

    def _load_settings(self) -> Dict[str, Any]:
        """Load user settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save user settings to file."""
        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings, f, indent=2)
            return True
        except IOError:
            return False

    def get_time_style(self) -> str:
        """Get the configured time style for display of timestamps."""
        return self.settings.get("time_style", DEFAULT_TIME_STYLE)
        
    def set_time_style(self, style: str) -> bool:
        """Set the time style preference."""
        if style not in ["iso", "human", "relative"]:
            return False
            
        self.settings["time_style"] = style
        return self._save_settings(self.settings)

    def display_models_table(self, provider: str, models: List[Dict[str, Any]]) -> None:
        """Display a table of models for a provider"""
        try:
            table = Table(title=f"Available Models \nfor {provider}")
            
            # Add columns
            table.add_column("Model", style="bold")
            
            # Add Account column for Fireworks
            if provider.lower() == "fireworks":
                table.add_column("Account", style="cyan")
                
            table.add_column("Status")
            
            # Add rows
            for model in models:
                model_name = model.get("model", "")
                status = model.get("status", "")
                
                # If Fireworks, include the account
                if provider.lower() == "fireworks":
                    account = model.get("account", "fireworks")
                    table.add_row(model_name, account, status)
                else:
                    table.add_row(model_name, status)
            
            console.print(table)
        except Exception as e:
            logger.warning(f"Error displaying models table: {e}")
            console.print(f"[bold red]Error displaying models: {str(e)}[/bold red]")


# Create a singleton config instance
config = Config()
