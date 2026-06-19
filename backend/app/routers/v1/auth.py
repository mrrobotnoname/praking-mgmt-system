from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import User
from app.db.session import get_session
from sqlmodel import select, Session
from pydantic import BaseModel
from app.core.security import create_token

router = APIRouter()

class LoginRequest(BaseModel):
    username:str
    password:str

@router.post("/login")
def login(payload: LoginRequest, db: Session=Depends(get_session)):
    user= db.exec(select(User).where(User.username == payload.username)).first()

    if not user:
        raise HTTPException(status_code=401,detail="Invalid username")
    if user.password != payload.password :
        raise HTTPException(status_code=401,detail="Invalid Password")
    
    jwt_token = create_token(subject=user.name,role=user.role)

    return{
        "access_token":jwt_token,
        "token_type":"bearer",
        "role":user.role,
        "Name":user.name
    }