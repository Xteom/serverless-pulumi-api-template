#!/bin/bash
set -e

# Show AWS identity for debugging purposes
aws sts get-caller-identity

# Set variables
API_NAME=${API_NAME:-"default-api"}
PULUMI_STATE_BUCKET=${PULUMI_STATE_BUCKET:-""}
USE_AUTOMATION_API=${USE_AUTOMATION_API:-"true"}

# Navigate to the infrastructure directory
cd /code/infrastructure

if [ "$USE_AUTOMATION_API" = "true" ]; then
    echo "Using Pulumi Automation API for deployment"
    # Run the Python script that contains the Automation API code
    python __main__.py
else
    echo "Using Pulumi CLI for deployment"
    # Set Pulumi stack name dynamically based on API name
    STACK_NAME="${API_NAME}-stack"
    
    # If the stack doesn't exist, create it
    if ! pulumi stack select ${STACK_NAME} 2>/dev/null; then
        echo "Creating new Pulumi stack: ${STACK_NAME}"
        pulumi stack init ${STACK_NAME}
    fi
    
    # Run update
    pulumi up --yes
fi

echo "Deployment completed successfully!"