



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
secret_id = 'nutriproof-secrets'
credentials_path = "..//nuriproof-c5b89f17bf69.json"
project_id="nutriproof-1723"

# if this is running locally then GOOGLE_APPLICATION_CREDENTIALS should be defined
if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as fp:
        credentialsVal = json.load(fp)
    project_id = credentialsVal['project_id']

print("ProjectID: "+project_id)
config = load_secret(project_id,secret_id)
        
# Store secret values as attributes
PROJECT_ID = config.get("project_id")
LOCATION = config.get("location")
LAYOUT_PROCESSOR_ID = config.get("layout_processor_id")
OCR_PROCESSOR_ID = config.get("ocr_processor_id")
OPENAI_API_KEY = config.get("openai_api_key")
SSL_KEY = config.get("sslkey")
DOK2U_API_KEY = config.get("dok2u_editor_api_key")
GEMINI_API_KEY = config.get("gemini_api_key")

 
