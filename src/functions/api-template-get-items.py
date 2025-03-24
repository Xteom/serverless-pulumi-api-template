# src/functions/api-template-get-items.py
import json
from datetime import datetime
from common.storage import StorageClient

storage_client = StorageClient()

def handler(event, context):
    """
    Handle GET requests to retrieve items from storage.
    Supports filtering by date range and pagination.
    """
    try:
        print("Received event:", json.dumps(event, indent=2))  # Debug log
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        start_date = query_params.get('start')
        end_date = query_params.get('end')
        page = int(query_params.get('page', '1'))
        limit = int(query_params.get('limit', '10'))
        
        # Calculate pagination start index (0-based)
        start_index = (page - 1) * limit
        
        # Get tenant ID from the authorizer context
        tenant_id = None
        if event.get('requestContext', {}).get('authorizer', {}).get('tenantId'):
            tenant_id = event['requestContext']['authorizer']['tenantId']
        
        # Define filter function for date range if provided
        filter_func = None
        if start_date or end_date:
            def filter_by_date(item):
                item_date = item.get('created_at') or item.get('date') or item.get('timestamp')
                if not item_date:
                    return True  # If no date field, include by default
                
                # Handle date comparisons
                if start_date and end_date:
                    return start_date <= item_date <= end_date
                elif start_date:
                    return start_date <= item_date
                elif end_date:
                    return item_date <= end_date
                
                return True
            
            filter_func = filter_by_date
        
        # Query items from storage
        prefix = f"tenants/{tenant_id}/" if tenant_id else ""
        result = storage_client.query_items(
            prefix=prefix,
            filter_func=filter_func,
            start=start_index,
            limit=limit
        )
        
        # Extract just the data for the response
        items = [item['data'] for item in result['items']]
        
        # Build the response
        response = {
            'items': items,
            'pagination': {
                'total': result['total'],
                'page': page,
                'limit': limit,
                'pages': (result['total'] + limit - 1) // limit,
                'has_more': result['has_more']
            }
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps(response)
        }
    
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }