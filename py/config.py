



import os
import json
from google.cloud import secretmanager
from google.api_core.exceptions import GoogleAPIError


def load_secret( project_id:str, secret_id: str):
    """
    Accesses and parses the secret stored in Secret Manager.

    Args:
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        secret_payload = response.payload.data.decode("UTF-8")
        return json.loads(secret_payload)
            
    except GoogleAPIError as e:
        raise RuntimeError(f"Erreur lors de l'accès au secret : {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError("Le secret n'est pas un JSON valide.")

"""
Initialize the configuration by loading secrets and GCP project ID.

Args:
    secret_id (str): The secret name in Secret Manager.
    credentials_path (str): Local path to credentials (used in local dev).
"""
def get_config():
    """Load configuration from Secret Manager or environment variables."""
    secret_id = 'nutriproof-secrets'
    credentials_path = "..//nutriproof-29d95359dc1f.json"
    project_id = "nutriproof"

    # if this is running locally then GOOGLE_APPLICATION_CREDENTIALS should be defined
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        if os.path.exists(credentials_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as fp:
                credentialsVal = json.load(fp)
            project_id = credentialsVal['project_id']

    try:
        config = load_secret(project_id, secret_id)
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

 
