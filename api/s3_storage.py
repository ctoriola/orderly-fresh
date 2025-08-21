import boto3
import os
import logging
from typing import Optional

class S3Storage:
    def __init__(self, bucket_name: str, session: Optional[boto3.Session] = None):
        self.bucket_name = bucket_name
        self.s3 = session.client('s3') if session else boto3.client('s3')
        logging.info(f"Initialized S3 connection to bucket {bucket_name}")

    def upload_file(self, file_path: str, s3_key: str) -> bool:
        """Upload a file to S3"""
        try:
            self.s3.upload_file(file_path, self.bucket_name, s3_key)
            logging.debug(f"Uploaded {file_path} to s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            logging.error(f"Error uploading file to S3: {str(e)}")
            raise

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download a file from S3"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.s3.download_file(self.bucket_name, s3_key, local_path)
            logging.debug(f"Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except Exception as e:
            logging.error(f"Error downloading file from S3: {str(e)}")
            raise

    def delete_file(self, s3_key: str) -> bool:
        """Delete a file from S3"""
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logging.debug(f"Deleted s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            logging.error(f"Error deleting file from S3: {str(e)}")
            raise

    def get_file_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Get a presigned URL for a file"""
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            logging.debug(f"Generated presigned URL for s3://{self.bucket_name}/{s3_key}")
            return url
        except Exception as e:
            logging.error(f"Error generating presigned URL: {str(e)}")
            raise
