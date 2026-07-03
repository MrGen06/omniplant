from fastapi import FastAPI
from backend.api.routers import auth, users
from backend.core.database import engine, Base, SessionLocal
from backend.models.user import UserModel

# Autogenerate database tables
Base.metadata.create_all(bind=engine)

# Seed Database if completely empty
db = SessionLocal()
if db.query(UserModel).count() == 0:
    db.add(UserModel(employee_id="EMP-1042", name="Ramesh", role_tier=1, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-2088", name="Priya", role_tier=2, password_hash=UserModel.hash_password("password123")))
    db.add(UserModel(employee_id="EMP-9001", name="Mr. Sharma", role_tier=3, password_hash=UserModel.hash_password("password123")))
    db.commit()
db.close()

app = FastAPI(title="OmniPlant.AI Production-Level Engine")
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Admin User Management"])