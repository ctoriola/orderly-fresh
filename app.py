import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from queue_system import QueueSystem
from models import User, users
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

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

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

@app.route('/scan')
def scanner():
    """Dedicated QR code scanner page"""
    return render_template('scanner.html')

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
    receipt_file = request.files.get('receipt')
    
    # Debug logging for receipt file
    if receipt_file:
        app.logger.info(f"Receipt file received: {receipt_file.filename}, content_type: {getattr(receipt_file, 'content_type', 'unknown')}")
    else:
        app.logger.info("No receipt file received")
    
    if not all([location_id, user_name]):
        flash('Missing required fields', 'error')
        return redirect(url_for('queue_page', location_id=location_id))
    
    queue_id = queue_system.join_queue(location_id, user_name, phone, notes, receipt_file)
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = users.get(username)
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('admin_index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Successfully logged out', 'success')
    return redirect(url_for('index'))

def requires_super_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            flash('You need super admin privileges to access this page', 'error')
            return redirect(url_for('admin_index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/queue/admin')
@login_required
def admin_index():
    locations = queue_system.get_all_locations()
    return render_template('queue_admin.html', locations=locations)

@app.route('/super-admin')
@login_required
@requires_super_admin
def super_admin():
    admin_list = [user for user in users.values() if not user.is_super_admin]
    return render_template('super_admin.html', admins=admin_list)

@app.route('/super-admin/create-admin', methods=['GET', 'POST'])
@login_required
@requires_super_admin
def create_admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        location_limit = int(request.form.get('location_limit', 5))
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('create_admin'))
        
        if username in users:
            flash('Username already exists', 'error')
            return redirect(url_for('create_admin'))
        
        new_admin = User.create(
            username=username,
            password=password,
            is_super_admin=False,
            location_limit=location_limit,
            created_by=current_user.username
        )
        users[username] = new_admin
        flash('Admin created successfully', 'success')
        return redirect(url_for('super_admin'))
    
    return render_template('create_admin.html')

@app.route('/super-admin/edit-admin/<admin_id>', methods=['GET', 'POST'])
@login_required
@requires_super_admin
def edit_admin(admin_id):
    admin = users.get(admin_id)
    if not admin:
        flash('Admin not found', 'error')
        return redirect(url_for('super_admin'))
    
    if request.method == 'POST':
        location_limit = int(request.form.get('location_limit', 5))
        new_password = request.form.get('new_password')
        
        admin.location_limit = location_limit
        if new_password:
            admin.password_hash = generate_password_hash(new_password)
        
        flash('Admin updated successfully', 'success')
        return redirect(url_for('super_admin'))
    
    return render_template('edit_admin.html', admin=admin)

@app.route('/queue/admin/locations/create', methods=['GET', 'POST'])
@login_required
def admin_create_location():
    if request.method == 'POST':
        # Check if user can create more locations
        if not current_user.can_create_location():
            flash('You have reached your location creation limit', 'error')
            return redirect(url_for('admin_index'))
            
        name = request.form.get('name')
        description = request.form.get('description', '')
        capacity = int(request.form.get('capacity', 0))
        
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('admin_create_location'))
        
        try:
            # Get base URL for QR code
            base_url = request.url_root.rstrip('/')
            location_id = queue_system.create_location(name, description, capacity, base_url, created_by=current_user.username)
            # Increment the location count for the user
            current_user.increment_location_count()
            
            # Verify location count hasn't exceeded limit
            if not current_user.is_super_admin and current_user.created_locations > current_user.location_limit:
                # Delete the location we just created
                queue_system.delete_location(location_id)
                flash('You have exceeded your location creation limit', 'error')
                return redirect(url_for('admin_index'))
            flash('Location created successfully!', 'success')
            return redirect(url_for('admin_manage_location', location_id=location_id))
        except Exception as e:
            flash(f'Error creating location: {str(e)}', 'error')
            return redirect(url_for('admin_create_location'))
    
    return render_template('queue_admin_create.html')

@app.route('/qr/<path:filename>')
def serve_qr(filename):
    """Serve QR codes from S3"""
    if not queue_system.s3:
        return "S3 storage not configured", 500
        
    try:
        # Remove any 'qrcodes/' prefix if it exists in the filename
        if filename.startswith('qrcodes/'):
            filename = filename[8:]  # Remove 'qrcodes/' prefix
        url = queue_system.s3.get_file_url(f"qrcodes/{filename}")
        return redirect(url)
    except Exception as e:
        return str(e), 500

@app.route('/receipt/<location_id>/<queue_id>')
@login_required
def view_receipt(location_id, queue_id):
    """View receipt for a queue entry"""
    # Get the queue entry
    location = queue_system.get_location(location_id)
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('admin_index'))
    
    # Find the queue entry
    queue_entry = None
    for entry in location.get('current_queue', []):
        if entry.get('id') == queue_id:
            queue_entry = entry
            break
    
    if not queue_entry:
        flash('Queue entry not found', 'error')
        return redirect(url_for('admin_manage_location', location_id=location_id))
    
    if not queue_entry.get('receipt_path'):
        flash('No receipt uploaded for this entry', 'error')
        return redirect(url_for('admin_manage_location', location_id=location_id))
    
    receipt_path = queue_entry['receipt_path']
    
    # Handle different receipt storage types
    if receipt_path.startswith('data:'):
        # Base64 data URL - display directly in template
        return render_template('view_receipt.html', 
                             queue_entry=queue_entry, 
                             location=location,
                             receipt_path=receipt_path)
    if queue_system.s3 and receipt_path.startswith('receipts/'):
        try:
            receipt_url = queue_system.s3.get_file_url(receipt_path)
            return redirect(receipt_url)
        except Exception as e:
            flash(f'Error accessing receipt: {str(e)}', 'error')
            return redirect(url_for('admin_manage_location', location_id=location_id))
    
    # For local files, serve them directly
    return render_template('view_receipt.html', 
                         queue_entry=queue_entry, 
                         location=location,
                         receipt_path=receipt_path)

@app.route('/receipts/<filename>')
@login_required
def serve_receipt(filename):
    """Serve receipt files from local storage"""
    import os
    from flask import send_from_directory
    
    receipts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'receipts')
    
    if not os.path.exists(os.path.join(receipts_dir, filename)):
        return "Receipt not found", 404
        
    return send_from_directory(receipts_dir, filename)

@app.route('/queue/admin/locations/<location_id>')
def admin_manage_location(location_id):
    location = queue_system.get_location(location_id)
    if not location:
        flash('Location not found', 'error')
        return redirect(url_for('admin_index'))
    
    queue = queue_system.get_queue_list(location_id)
    stats = queue_system.get_queue_stats(location_id)
    
    # Update QR paths to use the new route
    if location.get('join_qr_path'):
        location['join_qr_path'] = os.path.basename(location['join_qr_path'])
    if location.get('status_qr_path'):
        location['status_qr_path'] = os.path.basename(location['status_qr_path'])
    
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
