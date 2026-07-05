from sqlalchemy import Column, String, Integer
import bcrypt
from core.database import Base

class UserModel(Base):
    __tablename__ = "users"

    employee_id = Column(String, primary_key=True, index=True) # e.g., EMP-1042
    name = Column(String, nullable=False)                      # e.g., Ramesh
    role_tier = Column(Integer, nullable=False)                # e.g., 1, 2, 3
    password_hash = Column(String, nullable=False)

    @staticmethod
    def hash_password(password: str) -> str:
        """Generates a secure cryptographic salt and hash."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        """Verifies an incoming plain-text password against the stored hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))