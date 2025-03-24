# pulumi/config.py
"""
Configuration file for API settings.
Modify this file to customize your API deployment.
"""

# API Configuration
API_CONFIG = {
    "name": "your-api-name",  # Change this to your API name
    "description": "Your API Description",
    "stage_name": "dev",      # Deployment stage (dev, prod, etc.)
    "region": "us-east-1"     # AWS region
}

# ECR Repository Configuration
ECR_CONFIG = {
    "repository": "your-ecr-repo-name",  # Change to your ECR repository name
    "account_id": "123456789012"         # Change to your AWS account ID
}

# S3 Bucket Configuration
STORAGE_CONFIG = {
    # Define your S3 buckets here
    "buckets": [
        {
            "name": "primary-data-bucket",
            "enable_versioning": True,
            "description": "Primary data storage"
        },
        {
            "name": "secondary-data-bucket",
            "enable_versioning": True,
            "description": "Secondary data storage"
        }
    ]
}

# Lambda Function Configuration
LAMBDA_CONFIG = {
    # Define your Lambda functions here
    "functions": [
        {
            "name": "authorizer",
            "memory": 2048,
            "timeout": 30,
            "environment_variables": {}
        },
        {
            "name": "get-items",
            "memory": 2048,
            "timeout": 30,
            "environment_variables": {
                "PRIMARY_BUCKET": "${primary-data-bucket}"
            }
        },
        {
            "name": "create-item",
            "memory": 2048,
            "timeout": 30,
            "environment_variables": {
                "PRIMARY_BUCKET": "${primary-data-bucket}"
            }
        },
        {
            "name": "update-item",
            "memory": 2048,
            "timeout": 30,
            "environment_variables": {
                "PRIMARY_BUCKET": "${primary-data-bucket}"
            }
        }
    ]
}

# API Endpoints Configuration
API_ENDPOINTS = {
    # Define your API endpoints here
    "resources": [
        {
            "path": "items",
            "methods": [
                {
                    "http_method": "GET",
                    "function": "get-items",
                    "requires_auth": True,
                    "query_parameters": ["start", "end", "page", "limit"]
                },
                {
                    "http_method": "POST",
                    "function": "create-item",
                    "requires_auth": True,
                    "query_parameters": []
                }
            ],
            "nested_resources": [
                {
                    "path": "{id}",
                    "methods": [
                        {
                            "http_method": "PUT",
                            "function": "update-item",
                            "requires_auth": True,
                            "query_parameters": []
                        }
                    ]
                }
            ]
        }
    ]
}

# Auth Configuration
AUTH_CONFIG = {
    "auth_api_url": "https://your-auth-api-url.amazonaws.com/auth/validate"
}