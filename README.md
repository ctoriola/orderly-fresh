# Orderly Queue Management System

A Flask-based queue management system that uses AWS DynamoDB for data storage and S3 for QR code storage. The system provides a web interface for managing queues and locations.

## Features

- Create and manage multiple queue locations
- Generate QR codes for each location
- Real-time queue status updates
- Admin interface for queue management
- AWS DynamoDB integration for data persistence
- AWS S3 integration for QR code storage
- Fallback to local storage when AWS is not configured

## Prerequisites

- Python 3.8 or higher
- AWS account (optional)
- AWS credentials (if using AWS services)

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your settings:
   ```
   cp .env.example .env
   ```
5. Configure your AWS credentials if using AWS services

## Configuration

Edit the `.env` file with your settings:

- `SECRET_KEY`: Flask secret key
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `AWS_REGION`: AWS region (default: us-east-1)
- `DYNAMODB_TABLE`: DynamoDB table name
- `S3_BUCKET`: S3 bucket name for QR codes

## Running the Application

1. Activate the virtual environment:
   ```
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Run the Flask application:
   ```
   python app.py
   ```

3. Access the application at `http://localhost:5000`

## Project Structure

- `api/` - AWS service integrations
  - `dynamodb_storage.py` - DynamoDB integration
  - `s3_storage.py` - S3 integration
- `static/` - Static files (CSS, JS, images)
- `templates/` - Jinja2 templates
- `tests/` - Unit and integration tests
- `instance/` - Instance-specific configuration
- `queue_system.py` - Core queue management logic
- `app.py` - Flask application entry point

## Development

1. Set up a virtual environment
2. Install development dependencies
3. Follow PEP 8 style guide
4. Write unit tests for new features
5. Handle errors gracefully with proper logging

## Testing

Run the tests using pytest:
```
pytest
```
