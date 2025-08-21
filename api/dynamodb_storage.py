import boto3
from typing import Dict, List, Optional
import logging

class DynamoDBQueueStorage:
    def __init__(self, table_name: str, session: Optional[boto3.Session] = None):
        self.table_name = table_name
        self.dynamodb = session.resource('dynamodb') if session else boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        logging.info(f"Initialized DynamoDB connection to table {table_name}")

    def list_locations(self) -> List[Dict]:
        """Get all locations from DynamoDB"""
        try:
            response = self.table.scan()
            locations = response.get('Items', [])
            logging.debug(f"Retrieved {len(locations)} locations from DynamoDB")
            return locations
        except Exception as e:
            logging.error(f"Error listing locations from DynamoDB: {str(e)}")
            raise

    def get_location(self, location_id: str) -> Optional[Dict]:
        """Get a specific location from DynamoDB"""
        try:
            response = self.table.get_item(Key={'location_id': location_id})
            location = response.get('Item')
            if location:
                logging.debug(f"Retrieved location {location_id} from DynamoDB")
            else:
                logging.debug(f"Location {location_id} not found in DynamoDB")
            return location
        except Exception as e:
            logging.error(f"Error getting location {location_id} from DynamoDB: {str(e)}")
            raise

    def put_location(self, location: Dict) -> bool:
        """Save a location to DynamoDB"""
        try:
            self.table.put_item(Item=location)
            logging.debug(f"Saved location {location.get('location_id')} to DynamoDB")
            return True
        except Exception as e:
            logging.error(f"Error saving location to DynamoDB: {str(e)}")
            raise

    def update_location(self, location_id: str, updates: Dict) -> bool:
        """Update a location in DynamoDB"""
        try:
            update_expression = "SET " + ", ".join(f"#{k} = :{k}" for k in updates.keys())
            expression_attribute_names = {f"#{k}": k for k in updates.keys()}
            expression_attribute_values = {f":{k}": v for k, v in updates.items()}

            self.table.update_item(
                Key={'location_id': location_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            logging.debug(f"Updated location {location_id} in DynamoDB")
            return True
        except Exception as e:
            logging.error(f"Error updating location in DynamoDB: {str(e)}")
            raise

    def delete_location(self, location_id: str) -> bool:
        """Delete a location from DynamoDB"""
        try:
            self.table.delete_item(Key={'location_id': location_id})
            logging.debug(f"Deleted location {location_id} from DynamoDB")
            return True
        except Exception as e:
            logging.error(f"Error deleting location from DynamoDB: {str(e)}")
            raise
