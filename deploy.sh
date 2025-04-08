#!/bin/bash
set -e

# Show AWS identity for debugging purposes
aws sts get-caller-identity

# Set API-specific variables with defaults
# Change the defaults or variable names as needed for your API
API_NAME=${API_NAME:-"your-api-name"}
PULUMI_STATE_BUCKET=${PULUMI_STATE_BUCKET:-""}
USE_AUTOMATION_API=${USE_AUTOMATION_API:-"true"}

# Set API-specific environment variables
# Add or remove variables as needed for your specific API
SERVICE_URL_1=${SERVICE_URL_1:-"https://example-service-1.com"}
SERVICE_URL_2=${SERVICE_URL_2:-"https://example-service-2.com"}
SERVICE_URL_3=${SERVICE_URL_3:-"https://example-service-3.com"}
AUTH_ENDPOINT=${AUTH_ENDPOINT:-"https://example-auth-endpoint.com"}

# Export environment variables for Pulumi
# These will be available to your Lambda functions
export SERVICE_URL_1
export SERVICE_URL_2
export SERVICE_URL_3
export AUTH_ENDPOINT

echo "Deploying ${API_NAME} API with configuration:"
echo "- API Name: $API_NAME"
echo "- State Bucket: $PULUMI_STATE_BUCKET"
echo "- Service URL 1: $SERVICE_URL_1"
echo "- Service URL 2: $SERVICE_URL_2"
echo "- Using Automation API: $USE_AUTOMATION_API"

# Navigate to the infrastructure directory
cd /code/infrastructure

if [ "$USE_AUTOMATION_API" = "true" ]; then
    echo "Using Pulumi Automation API for deployment"
    # Run the Python script that contains the Automation API code
    python __main__.py
else
    echo "Using Pulumi CLI for deployment"
    # Configure AWS
    aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID
    aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY
    aws configure set default.region $AWS_REGION
    
    pulumi login --local

    # Set Pulumi stack name dynamically based on API name
    STACK_NAME="${API_NAME}-stack"
    
    # If the stack doesn't exist, create it
    if ! pulumi stack select ${STACK_NAME} 2>/dev/null; then
        echo "Creating new Pulumi stack: ${STACK_NAME}"
        pulumi stack init ${STACK_NAME}
    fi
    
    # Set Pulumi configuration for API-specific services
    # Update these for your specific API needs
    pulumi config set service_url_1 "$SERVICE_URL_1"
    pulumi config set service_url_2 "$SERVICE_URL_2"
    
    # Run update
    pulumi up --yes
fi

echo "Deployment completed successfully!"