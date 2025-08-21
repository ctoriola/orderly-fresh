"""
Example configuration file for the Orderly Queue System.
Copy this file to config.py in the instance folder and update with your values.
"""

# AWS Configuration
AWS_ACCESS_KEY_ID = 'your-access-key-id'
AWS_SECRET_ACCESS_KEY = 'your-secret-access-key'
AWS_REGION = 'us-east-1'

# DynamoDB Configuration
DYNAMODB_TABLE = 'orderly-queues'

# S3 Configuration
S3_BUCKET = 'orderly-qrcodes'

# Flask Configuration
SECRET_KEY = 'your-secret-key-here'  # Change this to a random secret key
DEBUG = False  # Set to True for development
