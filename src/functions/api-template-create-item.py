# src/functions/api-template-create-item.py
import json
from datetime import datetime
import uuid
from common.storage import StorageClient

storage_client = StorageClient()

# Define required fields for your item data
REQUIRED_FIELDS = ['name', 'description']

def handler(event, context):
    """
    Handle POST requests to create a new item in storage.
    """
    try:
        print("Received event:", json.dumps(event, indent=2))  # Debug log
        
        # Validate request
        if 'body' not in event:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid request body'})
            }

        # Parse the request body
        body = json.loads(event['body'])
        
        # Get tenant ID from the authorizer context
        tenant_id = None
        if event.get('requestContext', {}).get('authorizer', {}).get('tenantId'):
            tenant_id = event['requestContext']['authorizer']['tenantId']
        
        # Validate required fields
        is_valid, missing_fields = storage_client.validate_item_data(body, REQUIRED_FIELDS)
        if not is_valid:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Missing required fields: {", ".join(missing_fields)}'})
            }
        
        # Prepare the item data
        item_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        new_item = {
            'id': item_id,
            'created_at': timestamp,
            'updated_at': timestamp,
            'tenant_id': tenant_id,
            **body  # Include all fields from the request body
        }
        
        # Determine the storage key based on tenant
        key_prefix = f"tenants/{tenant_id}/" if tenant_id else "items/"
        key = f"{key_prefix}{item_id}.json"
        
        # Save the new item
        result = storage_client.write_item(new_item, key)
        
        if result:
            return {
                'statusCode': 201,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(new_item)
            }
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Failed to save item'})
            }
            
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }