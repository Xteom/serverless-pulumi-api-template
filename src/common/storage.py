# src/common/storage.py

import boto3
import json
import os
import uuid
from datetime import datetime

class StorageClient:
    """
    Generic Storage Client for S3 operations.
    This replaces the specific s3_operations.py with a more versatile interface.
    """
    
    def __init__(self, bucket_name=None):
        """
        Initialize the storage client with optional bucket name.
        If not provided, will try to get from environment variables.
        """
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name or os.environ.get('PRIMARY_BUCKET')
        
        if not self.bucket_name:
            raise ValueError("Bucket name must be provided or set in environment variables")

    def list_items(self, prefix='', max_items=1000):
        """List items in the bucket with the given prefix."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_items
            )
            return response.get('Contents', [])
        except Exception as e:
            print(f"Error listing items: {str(e)}")
            return []
    
    def get_item(self, key):
        """Get an item from the bucket by key."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"Error getting item {key}: {str(e)}")
            return None
    
    def write_item(self, data, key=None):
        """
        Write an item to the bucket.
        If key is not provided, generates a UUID-based key.
        """
        if key is None:
            # Generate a key based on current timestamp and UUID
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            key = f"items/{timestamp}-{str(uuid.uuid4())}.json"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(data),
                ContentType='application/json'
            )
            return key
        except Exception as e:
            print(f"Error writing item: {str(e)}")
            return None
    
    def update_item(self, key, data):
        """Update an existing item by key."""
        try:
            # First check if the item exists
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            # If no exception, update the item
            return self.write_item(data, key)
        except Exception as e:
            print(f"Error updating item {key}: {str(e)}")
            return None
    
    def delete_item(self, key):
        """Delete an item by key."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except Exception as e:
            print(f"Error deleting item {key}: {str(e)}")
            return False
    
    def query_items(self, prefix='', filter_func=None, start=0, limit=100):
        """
        Query items with prefix and optional filtering.
        Supports pagination with start and limit parameters.
        """
        items = []
        try:
            all_items = self.list_items(prefix)
            
            # Sort by last modified date (newest first)
            all_items.sort(key=lambda x: x.get('LastModified', 0), reverse=True)
            
            # Apply filtering if provided
            if filter_func:
                filtered_items = []
                for item_meta in all_items:
                    item_data = self.get_item(item_meta['Key'])
                    if item_data and filter_func(item_data):
                        filtered_items.append({
                            'metadata': item_meta,
                            'data': item_data
                        })
                all_items = filtered_items
            else:
                # Get full data for each item
                all_items_with_data = []
                for item_meta in all_items:
                    item_data = self.get_item(item_meta['Key'])
                    if item_data:
                        all_items_with_data.append({
                            'metadata': item_meta,
                            'data': item_data
                        })
                all_items = all_items_with_data
            
            # Apply pagination
            end = min(start + limit, len(all_items))
            items = all_items[start:end]
            
            return {
                'items': items,
                'total': len(all_items),
                'start': start,
                'limit': limit,
                'has_more': end < len(all_items)
            }
        except Exception as e:
            print(f"Error querying items: {str(e)}")
            return {
                'items': [],
                'total': 0,
                'start': start,
                'limit': limit,
                'has_more': False,
                'error': str(e)
            }
    
    def validate_item_data(self, data, required_fields=None):
        """
        Validate if all required fields are present in the data.
        Returns (is_valid, missing_fields)
        """
        if required_fields is None:
            return True, []
        
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        return len(missing_fields) == 0, missing_fields