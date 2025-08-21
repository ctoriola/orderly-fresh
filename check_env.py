import os
from dotenv import load_dotenv

def check_env():
    load_dotenv()
    
    # Check AWS credentials
    aws_keys = {
        'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
        'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'AWS_REGION': os.getenv('AWS_REGION'),
        'DYNAMODB_TABLE': os.getenv('DYNAMODB_TABLE'),
        'S3_BUCKET': os.getenv('S3_BUCKET')
    }
    
    print("Checking environment variables:")
    for key, value in aws_keys.items():
        status = "✓" if value else "✗"
        if value and key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']:
            value = value[:6] + '...'  # Show only first 6 characters
        print(f"{status} {key}: {value}")
