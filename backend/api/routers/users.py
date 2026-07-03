from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.models.user import UserModel
from backend.core.security import create_access_token
from typing import List

router = APIRouter()

# --- Request Validation Schemas ---
class UserCreate(BaseModel):
    employee_id: str = Field(..., example="EMP-5011")
    name: str = Field(..., example="Amit Kumar")
    role_tier: int = Field(..., ge=1, le=3, description="Role tier must be 1, 2, or 3")
    password: str = Field(..., min_length=6, example="securePassword123")

class UserResponse(BaseModel):
    employee_id: str
    name: str
    role_tier: int

    class Config:
        from_attributes = True


# --- Administrative CRUD Endpoints ---

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def add_employee(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Administrative Endpoint: Adds a new employee to the database.
    Automatically encrypts the plain-text password using Bcrypt before storage.
    """
    existing_user = db.query(UserModel).filter(UserModel.employee_id == user_data.employee_id.upper()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with Employee ID {user_data.employee_id} already exists."
        )
    
    new_user = UserModel(
        employee_id=user_data.employee_id.upper(),
        name=user_data.name,
        role_tier=user_data.role_tier,
        password_hash=UserModel.hash_password(user_data.password)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.delete("/{employee_id}", status_code=status.HTTP_200_OK)
async def delete_employee(employee_id: str, db: Session = Depends(get_db)):
    """
    Administrative Endpoint: Deletes an employee from the database by their Employee ID.
    """
    target_user = db.query(UserModel).filter(UserModel.employee_id == employee_id.upper()).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee ID {employee_id} not found in the corporate registry."
        )
    
    db.delete(target_user)
    db.commit()
    return {"detail": f"Employee {employee_id.upper()} successfully de-provisioned and removed."}

@router.get("/", response_model=list[UserResponse])
async def get_all_employees(db: Session = Depends(get_db)):
    """
    Administrative Endpoint: Retrieves a complete list of all registered employees.
    Password hashes are automatically excluded via the UserResponse model schema.
    """
    users = db.query(UserModel).all()
    return users