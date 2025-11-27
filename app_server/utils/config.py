from typing import Dict, Any
import os
import json
from dotenv import load_dotenv

load_dotenv()

def read_secret(secret_name: str) -> str:
    """ Read a secret from environment variables or file. 
    The file will be in /etc/secrets/secret_name.
    Trim the string after reading the file and then return it"""
    
    # Check environment variable first
    env_secret = os.getenv(secret_name) or os.getenv(secret_name.upper())
    if env_secret:
        return env_secret

    if os.path.exists(f"/etc/secrets/{secret_name}"):
        secret_path = f"/etc/secrets/{secret_name}"
        with open(secret_path, 'r', encoding='utf-8') as file:
            secret = file.read().strip()
    elif os.path.exists(f"/etc/secrets/{secret_name}.txt"):
        secret_path = f"/etc/secrets/{secret_name}.txt"
        with open(secret_path, 'r', encoding='utf-8') as file:
            secret = file.read().strip()
    else:
        # Fallback or raise error depending on strictness. 
        # For now, raising error as per original logic if not found anywhere.
        raise FileNotFoundError(f"Secret {secret_name} not found in environment or /etc/secrets/")

    return secret

def get_headers() -> Dict[str, str]:
    """ Get the headers for the API call. """
    headers = {
        "Content-Type": "application/json",
        "X-API-key": read_secret("api_key"),
    }
    return headers

def get_config_value(key: str) -> Any:
    """
    Read a value from the config.json file at the repository root.

    Args:
        key: The key to look up in the config.json file

    Returns:
        The value associated with the key in the config.json file

    Raises:
        KeyError: If the key is not found in the config
        FileNotFoundError: If the config.json file is not found
    """
    # Get the path to the repository root
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(repo_root, 'config.json')

    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    if key not in config:
        raise KeyError(f"Key '{key}' not found in config.json")

    return config[key]
