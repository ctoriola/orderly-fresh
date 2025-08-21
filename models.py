from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, password_hash, is_super_admin=False, location_limit=5, created_by=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_super_admin = is_super_admin
        self.location_limit = location_limit
        self.created_by = created_by
        self.created_locations = 0  # Track number of locations created
    
    @staticmethod
    def create(username, password, is_super_admin=False, location_limit=5, created_by=None):
        """Create a new user with hashed password"""
        password_hash = generate_password_hash(password)
        return User(username, username, password_hash, is_super_admin, location_limit, created_by)
    
    def check_password(self, password):
        """Check if the provided password matches"""
        return check_password_hash(self.password_hash, password)
    
    def can_create_location(self):
        """Check if the user can create more locations"""
        return self.is_super_admin or self.created_locations < self.location_limit
    
    def increment_location_count(self):
        """Increment the count of created locations"""
        if not self.is_super_admin:
            self.created_locations += 1

# In-memory user storage for simplicity
# In production, use a proper database
users = {
    "superadmin": User("superadmin", "superadmin", generate_password_hash("superadmin"), is_super_admin=True, location_limit=float('inf')),
    "admin": User("admin", "admin", generate_password_hash("admin"), is_super_admin=False, location_limit=5)
}
