import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from queue_system import QueueSystem
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
    AWS_ACCESS_KEY_ID=os.environ.get('AWS_ACCESS_KEY_ID'),
    AWS_SECRET_ACCESS_KEY=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    AWS_REGION=os.environ.get('AWS_REGION', 'eu-north-1'),
    DYNAMODB_TABLE=os.environ.get('DYNAMODB_TABLE', 'orderlyqueues'),
    S3_BUCKET=os.environ.get('S3_BUCKET', 'ctorderly')
)

# Load instance config if it exists
if os.path.exists(os.path.join(app.instance_path, 'config.py')):
    app.config.from_pyfile('config.py')

# Ensure instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

# Initialize queue system
queue_system = QueueSystem(
    data_file='queue_data.json',
    s3_bucket=app.config['S3_BUCKET'],
    s3_region=app.config['AWS_REGION'],
    aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
    dynamodb_table=app.config['DYNAMODB_TABLE']
)

# Routes
@app.route('/')
def index():
    locations = queue_system.get_all_locations()
    active_queues = sum(1 for loc in locations if any(entry.get('status') == 'waiting' for entry in loc.get('current_queue', [])))
    return render_template('index.html', locations=locations, active_queues=active_queues)

@app.route('/find')
def find_location():
    """Find a location by its code"""
    code = request.args.get('code')
    if not code:
        flash('Please enter a location code', 'error')
        return redirect(url_for('index'))
        
    # Try to find the location
    location = queue_system.get_location(code)
    if location:
        return redirect(url_for('queue_page', location_id=code))
    else:
        flash('Location not found', 'error')
        return redirect(url_for('index'))

@app.route('/status_check/<location_id>')
def status_check_page(location_id):
    """Show status check page for a location"""
    location = queue_system.get_location(location_id)
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('index'))
    return render_template('status_check.html', location=location)

@app.route('/check_status')
def check_status():
    """Check queue status by queue ID"""
    queue_id = request.args.get('queue_id')
    location_id = request.args.get('location_id')  # Optional, from status check page
    
    if not queue_id:
        flash('Please enter your queue ID', 'error')
        return redirect(url_for('index'))
    
    # If location_id not provided, try to extract it from queue ID
    if not location_id:
        location_id = queue_system.get_location_from_queue_id(queue_id)
        if not location_id:
            flash('Invalid queue ID format', 'error')
            return redirect(url_for('index'))
    
    # Try to get the queue status
    status = queue_system.get_queue_position(location_id, queue_id)
    if status:
        return redirect(url_for('queue_status', location_id=location_id, queue_id=queue_id))
    else:
        flash('Queue entry not found. Please check your queue ID', 'error')
        if location_id:
            return redirect(url_for('status_check_page', location_id=location_id))
        return redirect(url_for('index'))

@app.route('/queue/<location_id>')
def queue_page(location_id):
    location = queue_system.get_location(location_id)
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('index'))
    stats = queue_system.get_queue_stats(location_id)
    return render_template('queue.html', location=location, stats=stats)

@app.route('/queue/join', methods=['POST'])
def join_queue():
    location_id = request.form.get('location_id')
    user_name = request.form.get('user_name')
    phone = request.form.get('phone', '')
    notes = request.form.get('notes', '')
    
    if not all([location_id, user_name]):
        flash('Missing required fields', 'error')
        return redirect(url_for('queue_page', location_id=location_id))
    
    queue_id = queue_system.join_queue(location_id, user_name, phone, notes)
    if queue_id:
        flash(f'Successfully joined the queue! Your Queue ID is: {queue_id} - Keep this ID to check your status later', 'success')
        return redirect(url_for('queue_status', location_id=location_id, queue_id=queue_id))
    
    flash('Failed to join queue', 'error')
    return redirect(url_for('queue_page', location_id=location_id))

@app.route('/queue/status/<location_id>/<queue_id>')
def queue_status(location_id, queue_id):
    status = queue_system.get_queue_position(location_id, queue_id)
    if not status:
        flash('Queue entry not found', 'error')
        return redirect(url_for('index'))
    return render_template('status.html', status=status, location_id=location_id, queue_id=queue_id)

@app.route('/queue/leave/<location_id>/<queue_id>', methods=['POST'])
def leave_queue(location_id, queue_id):
    if queue_system.leave_queue(location_id, queue_id):
        flash('Successfully left the queue', 'success')
    else:
        flash('Error leaving queue', 'error')
    return redirect(url_for('index'))

@app.route('/queue/admin')
def admin_index():
    locations = queue_system.get_all_locations()
    return render_template('queue_admin.html', locations=locations)

@app.route('/queue/admin/locations/create', methods=['GET', 'POST'])
def admin_create_location():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        capacity = int(request.form.get('capacity', 0))
        
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('admin_create_location'))
        
        try:
            # Get base URL for QR code
            base_url = request.url_root.rstrip('/')
            location_id = queue_system.create_location(name, description, capacity, base_url)
            flash('Location created successfully!', 'success')
            return redirect(url_for('admin_manage_location', location_id=location_id))
        except Exception as e:
            flash(f'Error creating location: {str(e)}', 'error')
            return redirect(url_for('admin_create_location'))
    
    return render_template('queue_admin_create.html')

@app.route('/queue/admin/locations/<location_id>')
def admin_manage_location(location_id):
    location = queue_system.get_location(location_id)
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('admin_index'))
    
    queue = queue_system.get_queue_list(location_id)
    stats = queue_system.get_queue_stats(location_id)
    return render_template('queue_admin_location.html', 
                         location=location, 
                         queue=queue,
                         stats=stats)

@app.route('/queue/admin/locations/<location_id>/serve', methods=['POST'])
def admin_serve_next(location_id):
    served = queue_system.serve_next(location_id)
    if served:
        flash(f'Served {served["user_name"]}', 'success')
    else:
        flash('No one in queue', 'info')
    return redirect(url_for('admin_manage_location', location_id=location_id))

@app.route('/queue/admin/locations/<location_id>/delete', methods=['POST'])
def admin_delete_location(location_id):
    """Delete a location"""
    if queue_system.delete_location(location_id):
        flash('Location deleted successfully', 'success')
    else:
        flash('Failed to delete location', 'error')
    return redirect(url_for('admin_index'))

# API endpoints
@app.route('/api/queue/status/<location_id>/<queue_id>')
def api_queue_status(location_id, queue_id):
    status = queue_system.get_queue_position(location_id, queue_id)
    if not status:
        return jsonify({'error': 'Queue entry not found'}), 404
    return jsonify(status)

# Vercel requires the app variable to be exposed
if __name__ == '__main__':
    app.run(debug=True)
