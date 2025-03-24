# src/functions/api-template-update-item.py
import json
from datetime import datetime
from common.storage import StorageClient

storage_client = StorageClient()

def handler(event, context):
    """
    Handle PUT requests to update an existing item in storage.
    """
    try:
        print("Received event:", json.dumps(event, indent=2))  # Debug log
        
        # Validate request
        if 'body' not in event or 'pathParameters' not in event or 'id' not in event['pathParameters']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid request. Missing body or item ID'})
            }

        # Parse the request body and get the item ID
        body = json.loads(event['body'])
        item_id = event['pathParameters']['id']
        
        # Get tenant ID from the authorizer context
        tenant_id = None
        if event.get('requestContext', {}).get('authorizer', {}).get('tenantId'):
            tenant_id = event['requestContext']['authorizer']['tenantId']
        
        # Determine the storage key based on tenant
        key_prefix = f"tenants/{tenant_id}/" if tenant_id else "items/"
        key = f"{key_prefix}{item_id}.json"
        
        # Get the existing item
        existing_item = storage_client.get_item(key)
        if not existing_item:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Item with ID {item_id} not found'})
            }
        
        # Verify tenant ownership if tenant ID is available
        if tenant_id and existing_item.get('tenant_id') != tenant_id:
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Not authorized to update this item'})
            }
        
        # Update the item with new data, preserving ID and creation timestamp
        updated_item = {
            **existing_item,
            **body,
            'id': item_id,  # Ensure ID doesn't change
            'created_at': existing_item.get('created_at'),  # Preserve creation timestamp
            'updated_at': datetime.now().isoformat(),  # Update the "updated_at" timestamp
            'tenant_id': existing_item.get('tenant_id')  # Preserve tenant ID
        }
        
        # Save the updated item
        result = storage_client.update_item(key, updated_item)
        
        if result:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(updated_item)
            }
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Failed to update item'})
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