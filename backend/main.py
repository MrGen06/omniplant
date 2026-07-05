import os
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Import Auth Layer Components
from api.routers import auth, ingest, users
from core.database import engine, Base, SessionLocal
from core.auth_middleware import CredentialMiddleware
from models.user import UserModel

# Import Priyanshu's Connection Components
from connection.neo_4j import connect_to_neo4j
from connection.llama_parse import parse_pdf

# RUN SQLITE DATABASE MIGRATIONS & SEED DATA
Base.metadata.create_all(bind=engine)

db = SessionLocal()
if db.query(UserModel).count() == 0:
    db.add(UserModel(employee_id="EMP-1042", name="Ramesh", role_tier=1, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-2088", name="Priya", role_tier=2, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-9001", name="Mr. Sharma", role_tier=3, password_hash=UserModel.hash_password("password123")))
    db.commit()
db.close()

# INITIALIZE THE SINGLE CORE FASTAPI INSTANCE
app = FastAPI(title="OmniPlant.AI Production-Level Engine")

# Protect ingest routes with bearer-token validation before request handlers run.
app.add_middleware(CredentialMiddleware)

# START UP LIFECYCLE INITIALIZATIONS 
# Connect to Neo4j database
# connect_to_neo4j()

# Parse PDF file using LlamaParse
# parse_pdf()

# MOUNT ARCHITECTURAL ROUTERS
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Admin User Management"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["PDF Ingestion"])

# APPLICATION ENTRY POINT

from services.ingest_synthetic_pdfs import ingest_pdf_path
if __name__ == "__main__":
    
    ingest_pdf_path("sample_50_words (1).pdf")
    
    

    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)