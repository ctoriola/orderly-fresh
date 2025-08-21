from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    
    @staticmethod
    def create(username, password):
        """Create a new user with hashed password"""
        password_hash = generate_password_hash(password)
        return User(username, username, password_hash)
    
    def check_password(self, password):
        """Check if the provided password matches"""
        return check_password_hash(self.password_hash, password)

# In-memory user storage for simplicity
# In production, use a proper database
users = {
    "admin": User("admin", "admin", generate_password_hash("admin"))  # Default admin/admin credentials
}
