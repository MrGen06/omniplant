import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Locate .env in the backend root directory (parent of core/)
backend_root = Path(__file__).resolve().parent.parent
env_path = backend_root / ".env"
load_dotenv(dotenv_path=env_path)

# Fetch POSTGRE_URL or fallback DATABASE_URL
DATABASE_URL = os.getenv("POSTGRE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "POSTGRE_URL (or DATABASE_URL) is missing from your backend/.env file!\n"
        "Please paste your Supabase connection URI into backend/.env as:\n"
        "POSTGRE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
    )

# Fix legacy postgres:// prefix if present
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Initialize standard engine hooks for PostgreSQL
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency injection provider for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()