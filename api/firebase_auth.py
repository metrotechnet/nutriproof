from functools import wraps
from flask import request, jsonify
import firebase_admin
from firebase_admin import credentials, auth

# Initialize Firebase Admin SDK
# Option 1: With service account key file (recommended for production)
#   Place your serviceAccountKey.json in the project root or dbase/ folder
#   cred = credentials.Certificate("path/to/serviceAccountKey.json")
#   firebase_admin.initialize_app(cred)
#
# Option 2: With project ID only (works for token verification without service account)
firebase_admin.initialize_app(options={
    'projectId': 'imx-nutriproof',
})


def require_auth(f):
    """
    Decorator that verifies the Firebase ID token from the Authorization header.
    Usage: @require_auth on any Flask route.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token manquant'}), 401
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            request.firebase_user = decoded_token
        except Exception:
            return jsonify({'error': 'Token invalide ou expiré'}), 401
        
        return f(*args, **kwargs)
    return decorated
