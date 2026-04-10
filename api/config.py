

import os
import json


def get_config():
    """Load configuration from local JSON file."""
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "nutriproof-secrets.json")
    try:
        with open(secrets_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Warning: Could not load secrets: {e}")
        return {}

# Initialize config lazily
_config = None

def _get(key, default=""):
    global _config
    if _config is None:
        _config = get_config()
    return _config.get(key, default)

def get_openai_api_key():
    return _get("openai_api_key")

def get_ssl_key():
    return _get("sslkey")

def get_dok2u_api_key():
    return _get("dok2u_editor_api_key")
