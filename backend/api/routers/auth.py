from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.user import UserModel
from core.security import create_access_token

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    role_tier: int
    employee_id: str
    name: str

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """Authenticates users dynamically against SQLite using secure Bcrypt hashing."""
    user_id = form_data.username.upper()
    
    # Query database dynamically
    user = db.query(UserModel).filter(UserModel.employee_id == user_id).first()
    
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication Failed: Invalid Employee ID or Password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.employee_id, "role": user.role_tier, "name": user.name}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role_tier": user.role_tier,
        "employee_id": user.employee_id,
        "name": user.name,
    }

