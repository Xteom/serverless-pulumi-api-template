# pulumi/config.py
"""
Configuration file for API settings.
Replace placeholders with your API-specific configuration.
"""

# API Configuration
API_CONFIG = {
    "name": "your-api-name",  # Change to your API name (e.g., "ba", "inventory", etc.)
    "description": "Your API Description",
    "stage_name": "dev",      # Deployment stage (dev, prod, etc.)
    "region": "us-east-1"     # AWS region
}

# ECR Repository Configuration
ECR_CONFIG = {
    "repository": "your-ecr-repository",  # Change to your ECR repository name
    "account_id": "123456789012"          # Change to your AWS account ID
}

# S3 Bucket Configuration
STORAGE_CONFIG = {
    # Define any S3 buckets your API needs, or leave empty if not required
    "buckets": []
}

# Lambda Function Configuration
LAMBDA_CONFIG = {
    "functions": [
        {
            # Authorizer function (change name to match your API naming convention)
            "name": "api-your-api-name-authorizer",
            "memory": 2048,
            "timeout": 30,
            "environment_variables": {
                # Add any environment variables needed by your authorizer
                "AUTH_API_URL": "https://your-auth-api-url.example.com"
            }
        },
        {
            # Main API function (change name to match your API naming convention)
            "name": "api-your-api-name-main",
            "memory": 4096,
            "timeout": 60,
            "environment_variables": {
                # Add any environment variables needed by your API
                "EXAMPLE_API_URL": "https://example-api.com",
                "LOG_LEVEL": "INFO"
            }
        }
        # Add more Lambda functions as needed for your API
    ]
}

# API Endpoints Configuration
API_ENDPOINTS = {
    "resources": [
        {
            # Primary API resource path
            "path": "your-resource-path",  # e.g., "ba", "inventory", "users", etc.
            "methods": [
                {
                    # HTTP method configuration
                    "http_method": "POST",  # or "GET", "PUT", "DELETE", etc.
                    "function": "api-your-api-name-main",  # Lambda function name from LAMBDA_CONFIG
                    "requires_auth": True,  # Set to False if no authorization required
                    "query_parameters": []  # Add query parameters if needed
                }
                # Add more methods as needed (GET, PUT, DELETE, etc.)
            ],
            # Add nested resources if needed
            "nested_resources": []
        }
        # Add more API resources as needed
    ]
}

# Auth Configuration 
AUTH_CONFIG = {
    "auth_api_url": "https://your-auth-api-url.example.com"
}