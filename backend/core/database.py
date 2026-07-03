import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. FIND THE ABSOLUTE LOCATION OF THIS CONFIG FILE
# This evaluates to: .../backend/core/
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. NAVIGATE UP ONE LEVEL TO THE BACKEND ROOT FOLDER
# This evaluates to: .../backend/
backend_root = os.path.dirname(current_dir)

# 3. LINK THE DATABASE FILE STRING ABSOLUTELY TO THE BACKEND DIRECTORY
db_absolute_path = os.path.join(backend_root, "omniplant.db")

# 4. ENFORCE PRODUCTION-GRADE SQLITE CONNECTION STRINGS
# Generates: sqlite:///C:/Users/.../backend/omniplant.db
DATABASE_URL = f"sqlite:///{db_absolute_path}"

# Initialize standard engine hooks
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Crucial fallback setting for SQLite async handlers
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency injection provider for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()