import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Import Auth Layer Components
from api.routers import auth, ingest, users
from core.database import engine, Base, SessionLocal
from core.auth_middleware import CredentialMiddleware
from models.user import UserModel

# Import Connection Components
from connection.neo_4j import connect_to_neo4j
from connection.llama_parse import parse_pdf

# RUN SQLITE DATABASE MIGRATIONS & SEED DATA
Base.metadata.create_all(bind=engine)

db = SessionLocal()
if db.query(UserModel).count() == 0:
    db.add(UserModel(employee_id="EMP-1042", name="Ramesh", role_tier=1, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-2088", name="Priya", role_tier=2, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-9001", name="Mr. Sharma", role_tier=3, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-2023", name="Goutam", role_tier=3, password_hash=UserModel.hash_password("password123"))) # Added you for safety!
    db.commit()
db.close()

# Define Lifespan events to cleanly open and close database connections
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing System Lifespan: Connecting to Neo4j Graph Cluster...")
    # This wakes up Priyanshu's driver wrapper natively upon server launch
    connect_to_neo4j() 
    yield
    print("Shutting down System Lifespan...")

# INITIALIZE THE SINGLE CORE FASTAPI INSTANCE WITH LIFESPAN CONTROL
app = FastAPI(title="OmniPlant.AI Production-Level Engine", lifespan=lifespan)

# MOUNT ARCHITECTURAL ROUTERS
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Admin User Management"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["PDF Ingestion"])

# APPLICATION ENTRY POINT
if __name__ == "__main__":
    # Allows execution via direct python selection: 'python main.py'
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)