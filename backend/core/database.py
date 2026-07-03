from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Uses a local SQLite file for development; can be swapped to PostgreSQL via env vars later
DATABASE_URL = "sqlite:///./omniplant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency injection provider for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()