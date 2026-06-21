from fastapi import Depends, HTTPException, status
import jwt
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session,select

from app.models.user import User
from app.db.session import get_session
from app.core.security import SECRETE_KEY, ALGORITHEM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_session)
):
    "Check the jwt validation and return the user of the token"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload =  jwt.decode(token,SECRETE_KEY,algorithms=ALGORITHEM)
        if payload.get("sub") is None or payload.get("role") is None:
            raise credentials_exception
        return payload
    except jwt.PyJWTError:
        raise credentials_exception
    

def isAdmin(payload: dict = Depends(get_current_user)) -> User:
    """
    Takes the verified user and ensures their role is strictly 'admin'.
    """
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Administrator privileges required."
        )
    return payload