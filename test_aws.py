import boto3
import os
from dotenv import load_dotenv

def test_aws_connection():
    print("Testing AWS Connectivity...")
    
    # Load environment variables
    load_dotenv()
    
    # Get AWS configuration
    region = os.getenv('AWS_REGION', 'eu-north-1')
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    dynamodb_table = os.getenv('DYNAMODB_TABLE', 'orderlyqueues')
    s3_bucket = os.getenv('S3_BUCKET', 'ctorderly')
    
    print(f"Using Region: {region}")
    print(f"Access Key: {access_key[:6]}..." if access_key else "Access Key: Not found")
    
    # Create AWS session
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    try:
        # Test DynamoDB connection
        print("\nTesting DynamoDB connection...")
        dynamodb = session.resource('dynamodb')
        table = dynamodb.Table(dynamodb_table)
        table.scan(Limit=1)
        print("✓ Successfully connected to DynamoDB table:", dynamodb_table)
    except Exception as e:
        print("✗ DynamoDB connection failed:", str(e))
    
    try:
        # Test S3 connection
        print("\nTesting S3 connection...")
        s3 = session.client('s3')
        s3.head_bucket(Bucket=s3_bucket)
        print("✓ Successfully connected to S3 bucket:", s3_bucket)
    except Exception as e:
        print("✗ S3 connection failed:", str(e))

if __name__ == "__main__":
    test_aws_connection()
