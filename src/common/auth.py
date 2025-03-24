# src/common/auth.py

import requests
import json
import os
from config import AUTH_CONFIG  # Import from config if available

class AuthClient:
    """
    Authentication client for validating tokens with an external auth service.
    """
    
    def __init__(self):
        # Try to get auth API URL from environment or config
        self.auth_api_url = os.environ.get(
            'AUTH_API_URL', 
            AUTH_CONFIG.get('auth_api_url', 'https://your-auth-api-url/auth/validate')
        )

    def validate_token(self, api_key: str):
        """
        Validates a token with the authentication service.
        
        Args:
            api_key: The API key or token to validate
            
        Returns:
            Tuple of (is_valid, error_message, user_data)
        """
        try:
            # Strip "Bearer " prefix if present
            if api_key.startswith('Bearer '):
                api_key = api_key[7:]
            
            # Use the API key as Bearer tokens
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            response = requests.get(
                self.auth_api_url,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return True, "", user_data
            else:
                return False, f"Token validation failed with status code: {response.status_code}", None
                
        except Exception as e:
            return False, f"Authentication error: {str(e)}", None
    
    def get_user_info(self, api_key: str):
        """
        Gets user information from the token.
        
        Args:
            api_key: The API key or token
            
        Returns:
            User data dictionary or None if invalid
        """
        is_valid, _, user_data = self.validate_token(api_key)
        return user_data if is_valid else None