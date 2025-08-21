import pytest
from app import app, queue_system

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_route(client):
    """Test the index route"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Welcome to Orderly' in response.data

def test_create_location(client):
    """Test creating a new location"""
    response = client.post('/queue/admin/locations/create', data={
        'name': 'Test Location',
        'description': 'Test Description',
        'capacity': 10
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Test Location' in response.data

def test_join_queue(client):
    """Test joining a queue"""
    # First create a location
    response = client.post('/queue/admin/locations/create', data={
        'name': 'Test Queue',
        'description': 'Test Queue',
        'capacity': 5
    })
    location_id = queue_system.get_all_locations()[0]['location_id']
    
    # Then try to join the queue
    response = client.post('/queue/join', data={
        'location_id': location_id,
        'user_name': 'Test User',
        'phone': '1234567890',
        'notes': 'Test notes'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Successfully joined the queue' in response.data

def test_serve_next(client):
    """Test serving the next person in queue"""
    # First create a location
    response = client.post('/queue/admin/locations/create', data={
        'name': 'Service Queue',
        'description': 'Service Queue',
        'capacity': 5
    })
    location_id = queue_system.get_all_locations()[0]['location_id']
    
    # Add someone to the queue
    client.post('/queue/join', data={
        'location_id': location_id,
        'user_name': 'Test Customer',
        'phone': '1234567890'
    })
    
    # Serve next person
    response = client.post(f'/queue/admin/locations/{location_id}/serve', 
                         follow_redirects=True)
    assert response.status_code == 200
    assert b'Served Test Customer' in response.data

def test_leave_queue(client):
    """Test leaving a queue"""
    # First create a location
    response = client.post('/queue/admin/locations/create', data={
        'name': 'Leave Queue',
        'description': 'Leave Queue',
        'capacity': 5
    })
    location_id = queue_system.get_all_locations()[0]['location_id']
    
    # Add someone to the queue
    client.post('/queue/join', data={
        'location_id': location_id,
        'user_name': 'Leaving Customer',
        'phone': '1234567890'
    })
    
    # Get the queue ID from the current queue
    location = queue_system.get_location(location_id)
    queue_id = location['current_queue'][0]['id']
    
    # Leave the queue
    response = client.post(f'/queue/leave/{location_id}/{queue_id}', 
                         follow_redirects=True)
    assert response.status_code == 200
    assert b'Successfully left the queue' in response.data
