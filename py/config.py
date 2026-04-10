



import os
import json

# Set GOOGLE_APPLICATION_CREDENTIALS early, before any Google client is initialized
_credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "nutriproof-29d95359dc1f.json")
if os.path.exists(_credentials_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _credentials_path


def get_config():
    """Load configuration from local JSON file."""
    secrets_path = "./config/nutriproof-secrets.json"
    project_id = "nutriproof"

    if os.path.exists(_credentials_path):
        with open(_credentials_path, 'r') as fp:
            credentialsVal = json.load(fp)
        project_id = credentialsVal.get('project_id', project_id)

    try:
        with open(secrets_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("ProjectID: " + project_id)
        return config
    except Exception as e:
        print(f"Warning: Could not load secrets: {e}")
        return {}

# Initialize config lazily
_config = None

def get_project_id():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("project_id", "nutriproof")

def get_location():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("location", "us-central1")

def get_layout_processor_id():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("layout_processor_id", "")

def get_ocr_processor_id():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("ocr_processor_id", "")

def get_openai_api_key():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("openai_api_key", "")

def get_ssl_key():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("sslkey", "")

def get_dok2u_api_key():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("dok2u_editor_api_key", "")

def get_gemini_api_key():
    global _config
    if _config is None:
        _config = get_config()
    return _config.get("gemini_api_key", "")

 
