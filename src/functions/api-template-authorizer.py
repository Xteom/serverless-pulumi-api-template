# src/functions/api-template-authorizer.py
import json
from common.auth import AuthClient

auth_client = AuthClient()

def handler(event, context):
    print("Received event:", json.dumps(event, indent=2))  # Debug log
    
    # Extract API Key from the Authorization header
    headers = event.get("headers", {})
    api_key = headers.get("Authorization", "")
    
    if api_key == '':
        print("Empty API Key")
        return generate_policy('user', 'Deny', event['methodArn'])

    # Validate the token using the API Key as Bearer token
    is_valid, error, user_data = auth_client.validate_token(api_key)
    
    if not is_valid:
        print(f"Validation failed: {error}")
        return generate_policy('user', 'Deny', event['methodArn'])
    
    # Extract tenant ID or other context you want to pass to the functions
    tenant_id = user_data.get('tenantId')
    print(f"TenantId extracted: {tenant_id}") 

    print("Validation successful, user_data:", json.dumps(user_data, indent=2))
    return generate_policy('user', 'Allow', event['methodArn'], tenant_id)

def generate_policy(principal_id, effect, resource, context=None):
    """
    Generate an IAM policy document for API Gateway authorization.
    
    Args:
        principal_id: Identifier for the principal (user)
        effect: 'Allow' or 'Deny'
        resource: The resource ARN
        context: Optional context data to pass to the API
        
    Returns:
        Policy document as a dictionary
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }],
        }
    }
    
    # Add context if provided (will be accessible in the Lambda event)
    if context:
        policy['context'] = {
            'tenantId': context
        }
    
    return policy