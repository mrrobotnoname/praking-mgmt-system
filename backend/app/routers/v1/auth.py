from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
from app.db.session import get_session
from sqlmodel import select, Session
from pydantic import BaseModel
from app.core.security import create_token,verify_paasword

router = APIRouter()


@router.post("/login")
def login(data:OAuth2PasswordRequestForm=Depends(), db: Session=Depends(get_session)):
    user= db.exec(select(User).where(User.username == data.username)).first()

    if not user:
        raise HTTPException(status_code=401,detail="Invalid username")
    if  not verify_paasword(data.password, user.password):
        raise HTTPException(status_code=401,detail="Invalid Password")
    
    jwt_token = create_token(subject=user.username,role=user.role)

    return{
        "access_token":jwt_token,
        "token_type":"bearer",
        "role":user.role,
        "name":user.username
    }
