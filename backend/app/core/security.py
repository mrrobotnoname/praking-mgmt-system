from dotenv import load_dotenv
import os
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv(override=True)

SECRETE_KEY = os.getenv("SECRETE_KEY")
ALGORITHEM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720  # expire in 12 hours


def create_token(subject: str, role: str):
    """
    Genarate a jwt token with a username and role
    """

    expire = datetime.now(timezone.utc) + \
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    token_payload = {
        "sub": subject,
        "role": role,
        "exp": expire
    }
    jwt_token = jwt.encode(token_payload,SECRETE_KEY,algorithm=ALGORITHEM)
    return jwt_token