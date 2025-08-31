import json
import os
import uuid
import boto3
import qrcode
from datetime import datetime
from typing import List, Dict, Optional
from api.s3_storage import S3Storage
from api.dynamodb_storage import DynamoDBQueueStorage
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class QueueSystem:
    def __init__(self, data_file='queue_data.json', s3_bucket=None, s3_region=None, s3_key=None, aws_access_key_id=None, aws_secret_access_key=None, dynamodb_table=None):
        self.data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), data_file)
        self.s3_key = s3_key or data_file
        self.s3 = None
        self.dynamodb = None
        
        # Create AWS session for consistent credentials
        self.aws_session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=s3_region
        )
        
        if s3_bucket:
            self.s3 = S3Storage(
                bucket_name=s3_bucket,
                session=self.aws_session
            )
        if dynamodb_table:
            self.dynamodb = DynamoDBQueueStorage(
                table_name=dynamodb_table,
                session=self.aws_session
            )
        self.queues = {}
        self.load_queues()

    def load_queues(self):
        """Load queue data from DynamoDB if available, else from JSON file"""
        try:
            if self.dynamodb:
                logging.info("Loading locations from DynamoDB...")
                locations = self.dynamodb.list_locations()
                self.queues = {loc['location_id']: loc for loc in locations}
                logging.info(f"Loaded {len(self.queues)} locations from DynamoDB")
                return
        except Exception as e:
            logging.error(f"Error loading from DynamoDB: {str(e)}")
            logging.info("Falling back to local file...")
            
        # Fallback to local file
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.queues = json.load(f)
                logging.info(f"Loaded {len(self.queues)} locations from local file")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logging.error(f"Error loading from local file: {str(e)}")
                self.queues = {}
    
    def save_queues(self):
        """Save queue data to DynamoDB if available, else to JSON file"""
        try:
            if self.dynamodb:
                logging.info("Saving locations to DynamoDB...")
                for location_id, location in self.queues.items():
                    try:
                        self.dynamodb.put_location(location)
                        logging.debug(f"Successfully saved location {location_id}")
                    except Exception as e:
                        logging.error(f"Error saving location {location_id} to DynamoDB: {str(e)}")
                        # Try to save to local file as backup
                        with open(self.data_file, 'w', encoding='utf-8') as f:
                            json.dump(self.queues, f, indent=2, ensure_ascii=False)
                        logging.info("Saved to local file as backup")
                        raise  # Re-raise the exception after backup
                logging.info("Successfully saved all locations to DynamoDB")
            else:
                logging.info("Saving to local file...")
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.queues, f, indent=2, ensure_ascii=False)
                logging.info("Successfully saved to local file")
        except Exception as e:
            logging.error(f"Error in save_queues: {str(e)}")
            raise

    def get_all_locations(self) -> List[Dict]:
        """Get all locations"""
        try:
            if self.dynamodb:
                logging.info("Getting all locations from DynamoDB...")
                locations = self.dynamodb.list_locations()
                # Update local cache
                self.queues = {loc['location_id']: loc for loc in locations}
                logging.info(f"Retrieved {len(locations)} locations from DynamoDB")
                return locations
            
            logging.info("Getting all locations from local cache...")
            return list(self.queues.values())
        except Exception as e:
            logging.error(f"Error getting all locations: {str(e)}")
            # Return what we have in local cache as fallback
            return list(self.queues.values())

    def generate_qr_codes(self, location_id: str, base_url: str) -> tuple[Optional[str], Optional[str]]:
        """Generate QR codes for a location and return the filenames"""
        try:
            # Generate queue join QR code
            join_qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            join_qr.add_data(f"{base_url}/queue/{location_id}")
            join_qr.make(fit=True)
            join_image = join_qr.make_image(fill_color="black", back_color="white")

            # Generate status check QR code
            status_qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            status_qr.add_data(f"{base_url}/status_check/{location_id}")
            status_qr.make(fit=True)
            status_image = status_qr.make_image(fill_color="black", back_color="white")
            
            # Use temporary file in /tmp directory (writable in Vercel)
            tmp_join_path = os.path.join('/tmp', f"{location_id}_join.png")
            tmp_status_path = os.path.join('/tmp', f"{location_id}_status.png")
            
            # Save to temporary location
            join_image.save(tmp_join_path)
            status_image.save(tmp_status_path)
            
            logging.info(f"Generated QR codes temporarily at {tmp_join_path} and {tmp_status_path}")

            # Upload to S3
            if self.s3:
                try:
                    join_s3_key = f"qrcodes/{location_id}_join.png"
                    status_s3_key = f"qrcodes/{location_id}_status.png"
                    self.s3.upload_file(tmp_join_path, join_s3_key)
                    self.s3.upload_file(tmp_status_path, status_s3_key)
                    logging.info(f"Uploaded QR codes to S3: {join_s3_key}, {status_s3_key}")
                except Exception as e:
                    logging.error(f"Error uploading QR codes to S3: {str(e)}")
                finally:
                    # Clean up temporary files
                    try:
                        os.remove(tmp_join_path)
                        os.remove(tmp_status_path)
                    except Exception as e:
                        logging.error(f"Error cleaning up temporary files: {str(e)}")

            # Return just the filenames without the qrcodes/ prefix
            return f"{location_id}_join.png", f"{location_id}_status.png"
        except Exception as e:
            logging.error(f"Error generating QR codes: {str(e)}")
            return None, None
        except Exception as e:
            logging.error(f"Error generating QR code: {str(e)}")
            return None

    def create_location(self, name: str, description: str = "", capacity: int = 0, base_url: str = "", created_by: str = None) -> str:
        """Create a new location with queue"""
        try:
            location_id = str(uuid.uuid4())
            location = {
                'location_id': location_id,
                'name': name,
                'description': description,
                'capacity': capacity,
                'current_queue': [],
                'served_count': 0,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'created_by': created_by
            }
            
            # Generate QR codes
            if base_url:
                join_qr_path, status_qr_path = self.generate_qr_codes(location_id, base_url)
                if join_qr_path and status_qr_path:
                    location['join_qr_path'] = join_qr_path
                    location['status_qr_path'] = status_qr_path
            
            # Save to DynamoDB first if available
            if self.dynamodb:
                self.dynamodb.put_location(location)
                logging.info(f"Location saved to DynamoDB: {location_id}")
            
            # Update local cache
            self.queues[location_id] = location
            
            # Save to file if not using DynamoDB
            if not self.dynamodb:
                self.save_queues()
            
            logging.info(f"Created new location: {name} ({location_id})")
            return location_id
            
        except Exception as e:
            logging.error(f"Error creating location: {str(e)}")
            raise

    def get_location(self, location_id: str) -> Optional[Dict]:
        """Get location details"""
        try:
            if self.dynamodb:
                location = self.dynamodb.get_location(location_id)
                if location:
                    # Update local cache
                    self.queues[location_id] = location
                return location
            return self.queues.get(location_id)
        except Exception as e:
            logging.error(f"Error getting location {location_id}: {str(e)}")
            return self.queues.get(location_id)  # Fallback to local cache

    def get_queue_list(self, location_id: str) -> List[Dict]:
        """Get list of people currently in queue"""
        try:
            location = self.get_location(location_id)
            if not location:
                logging.warning(f"Location {location_id} not found")
                return []
            
            # Filter for only waiting entries and sort by position
            queue = [
                entry for entry in location.get('current_queue', [])
                if entry.get('status') == 'waiting'
            ]
            queue.sort(key=lambda x: x.get('position', 0))
            
            logging.info(f"Retrieved {len(queue)} waiting entries for location {location_id}")
            return queue
            
        except Exception as e:
            logging.error(f"Error getting queue list for location {location_id}: {str(e)}")
            return []

    def get_queue_stats(self, location_id: str) -> Dict:
        """Get queue statistics for a location"""
        try:
            location = self.get_location(location_id)
            if not location:
                logging.warning(f"Location {location_id} not found")
                return {
                    'location_name': '',
                    'waiting_count': 0,
                    'served_count': 0,
                    'total_served': 0,
                    'capacity': 0,
                    'estimated_wait': 0
                }
            
            waiting_count = len([
                e for e in location.get('current_queue', [])
                if e.get('status') == 'waiting'
            ])
            served_count = len([
                e for e in location.get('current_queue', [])
                if e.get('status') == 'served'
            ])
            
            stats = {
                'location_name': location.get('name', ''),
                'waiting_count': waiting_count,
                'served_count': served_count,
                'total_served': location.get('served_count', 0),
                'capacity': location.get('capacity', 0),
                'estimated_wait': self._estimate_wait_time(waiting_count)
            }
            
            logging.info(f"Retrieved stats for location {location_id}: {stats}")
            return stats
            
        except Exception as e:
            logging.error(f"Error getting queue stats for location {location_id}: {str(e)}")
            return {
                'location_name': '',
                'waiting_count': 0,
                'served_count': 0,
                'total_served': 0,
                'capacity': 0,
                'estimated_wait': 0
            }
    
    def _estimate_wait_time(self, position: int) -> int:
        """Estimate wait time in minutes based on position"""
        # Simple estimation: 5 minutes per person
        return position * 5
    
    def _save_receipt_file(self, receipt_file, queue_id: str) -> Optional[str]:
        """Save receipt file to S3 or local storage"""
        try:
            import os
            from werkzeug.utils import secure_filename
            
            # Check if file is valid
            if not receipt_file or not hasattr(receipt_file, 'filename') or not receipt_file.filename:
                logging.warning("Invalid receipt file provided")
                return None
            
            # Get file extension
            filename = secure_filename(receipt_file.filename)
            if not filename:
                logging.warning("Invalid filename after securing")
                return None
                
            file_ext = os.path.splitext(filename)[1].lower()
            
            # Create a unique filename
            receipt_filename = f"receipt_{queue_id}{file_ext}"
            
            # Reset file pointer to beginning
            receipt_file.seek(0)
            
            if self.s3:
                # Upload to S3
                try:
                    receipt_path = f"receipts/{receipt_filename}"
                    self.s3.upload_file_obj(receipt_file, receipt_path)
                    logging.info(f"Uploaded receipt to S3: {receipt_path}")
                    return receipt_path
                except Exception as e:
                    logging.error(f"Failed to upload receipt to S3: {str(e)}")
                    # Fall back to local storage
                    receipt_file.seek(0)  # Reset file pointer for local save
            
            # Save locally
            receipts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'receipts')
            os.makedirs(receipts_dir, exist_ok=True)
            
            local_path = os.path.join(receipts_dir, receipt_filename)
            receipt_file.save(local_path)
            logging.info(f"Saved receipt locally: {local_path}")
            return f"receipts/{receipt_filename}"
            
        except Exception as e:
            logging.error(f"Error saving receipt file: {str(e)}")
            return None
    
    def serve_next(self, location_id: str) -> Optional[Dict]:
        """Serve the next person in queue"""
        try:
            location = self.get_location(location_id)
            if not location:
                logging.warning(f"Location {location_id} not found")
                return None
            
            # Get the waiting queue sorted by position
            waiting_queue = [
                e for e in location.get('current_queue', [])
                if e.get('status') == 'waiting'
            ]
            waiting_queue.sort(key=lambda x: x.get('position', 0))
            
            if not waiting_queue:
                logging.info(f"No one waiting in queue at location {location_id}")
                return None
            
            # Get the first person in queue
            next_person = waiting_queue[0]
            next_person['status'] = 'served'
            next_person['served_at'] = datetime.now().isoformat()
            
            # Update location
            location['served_count'] = location.get('served_count', 0) + 1
            location['updated_at'] = datetime.now().isoformat()
            
            # Save changes
            if self.dynamodb:
                self.dynamodb.put_location(location)
            else:
                self.save_queues()
            
            logging.info(f"Served {next_person.get('user_name')} at location {location_id}")
            return next_person
            
        except Exception as e:
            logging.error(f"Error serving next person at location {location_id}: {str(e)}")
            return None

    def delete_location(self, location_id: str) -> bool:
        """Delete a location"""
        try:
            if not location_id in self.queues:
                logging.warning(f"Location {location_id} not found")
                return False

            # Delete from DynamoDB if available
            if self.dynamodb:
                try:
                    self.dynamodb.delete_location(location_id)
                    logging.info(f"Deleted location {location_id} from DynamoDB")
                except Exception as e:
                    logging.error(f"Error deleting location {location_id} from DynamoDB: {str(e)}")
                    return False

            # Delete from local cache
            del self.queues[location_id]
            
            # Save to file if not using DynamoDB
            if not self.dynamodb:
                self.save_queues()
            
            logging.info(f"Successfully deleted location {location_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error deleting location {location_id}: {str(e)}")
            return False

    def join_queue(self, location_id: str, user_name: str, phone: str = "", notes: str = "", receipt_file=None) -> Optional[str]:
        """Join a queue at a location"""
        try:
            location = self.get_location(location_id)
            if not location:
                logging.warning(f"Location {location_id} not found when trying to join queue")
                return None

            # Create queue entry with combined ID (location_id + unique ID)
            unique_id = str(uuid.uuid4())[:8]  # First 8 chars of UUID for shorter ID
            queue_id = f"{location_id[:8]}-{unique_id}"  # Format: LOCXXXXX-UNIQXXXX
            position = len([e for e in location.get('current_queue', []) if e.get('status') == 'waiting']) + 1
            
            # Handle receipt file upload
            receipt_path = None
            if receipt_file and hasattr(receipt_file, 'filename') and receipt_file.filename and receipt_file.filename.strip():
                receipt_path = self._save_receipt_file(receipt_file, queue_id)
                logging.info(f"Receipt upload attempted for queue_id {queue_id}, result: {receipt_path}")
            
            queue_entry = {
                'id': queue_id,
                'user_name': user_name,
                'phone': phone,
                'notes': notes,
                'receipt_path': receipt_path,
                'position': position,
                'joined_at': datetime.now().isoformat(),
                'status': 'waiting'  # waiting, served, left
            }

            # Initialize current_queue if it doesn't exist
            if 'current_queue' not in location:
                location['current_queue'] = []

            # Add to queue
            location['current_queue'].append(queue_entry)
            location['updated_at'] = datetime.now().isoformat()

            # Save changes
            if self.dynamodb:
                self.dynamodb.put_location(location)
            else:
                self.save_queues()

            logging.info(f"User {user_name} joined queue at location {location_id} with queue_id {queue_id}")
            return queue_id

        except Exception as e:
            logging.error(f"Error joining queue at location {location_id}: {str(e)}")
            return None

    def leave_queue(self, location_id: str, queue_id: str) -> bool:
        """Remove a person from queue"""
        try:
            location = self.get_location(location_id)
            if not location:
                logging.warning(f"Location {location_id} not found")
                return False

            # Find and update the queue entry
            for entry in location.get('current_queue', []):
                if entry.get('id') == queue_id and entry.get('status') == 'waiting':
                    entry['status'] = 'left'
                    entry['left_at'] = datetime.now().isoformat()
                    location['updated_at'] = datetime.now().isoformat()

                    # Recalculate positions for remaining people
                    waiting_entries = [e for e in location['current_queue'] if e.get('status') == 'waiting']
                    for pos, e in enumerate(sorted(waiting_entries, key=lambda x: x.get('position', 0)), 1):
                        e['position'] = pos

                    # Save changes
                    if self.dynamodb:
                        self.dynamodb.put_location(location)
                    else:
                        self.save_queues()

                    logging.info(f"User left queue at location {location_id} with queue_id {queue_id}")
                    return True

            logging.warning(f"Queue entry {queue_id} not found or not waiting at location {location_id}")
            return False

        except Exception as e:
            logging.error(f"Error leaving queue at location {location_id}: {str(e)}")
            return False

    def get_queue_position(self, location_id: str, queue_id: str) -> Optional[Dict]:
        """Get queue position and status for a user"""
        try:
            location = self.get_location(location_id)
            if not location:
                logging.warning(f"Location {location_id} not found")
                return None

            # Find the queue entry
            for entry in location.get('current_queue', []):
                if entry.get('id') == queue_id and entry.get('status') == 'waiting':
                    # Count total waiting
                    total_waiting = len([e for e in location['current_queue'] if e.get('status') == 'waiting'])
                    
                    return {
                        'position': entry.get('position', 0),
                        'total_in_queue': total_waiting,
                        'user_name': entry.get('user_name', ''),
                        'joined_at': entry.get('joined_at', ''),
                        'estimated_wait': self._estimate_wait_time(entry.get('position', 0))
                    }

            logging.warning(f"Queue entry {queue_id} not found or not waiting at location {location_id}")
            return None

        except Exception as e:
            logging.error(f"Error getting queue position for {queue_id} at location {location_id}: {str(e)}")
            return None

    def _estimate_wait_time(self, position: int) -> int:
        """Estimate wait time in minutes based on position"""
        # Assuming average of 5 minutes per person
        # Could be made more sophisticated based on historical data
        average_time_per_person = 5
        return position * average_time_per_person

    def get_location_from_queue_id(self, queue_id: str) -> Optional[str]:
        """Extract location ID from a queue ID"""
        try:
            # Queue ID format is LOCXXXXX-UNIQXXXX
            location_part = queue_id.split('-')[0]
            # Search through locations to find matching prefix
            for location_id in self.queues:
                if location_id.startswith(location_part):
                    return location_id
            return None
        except Exception as e:
            logging.error(f"Error extracting location from queue ID {queue_id}: {str(e)}")
            return None
