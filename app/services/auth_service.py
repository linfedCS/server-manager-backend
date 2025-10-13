from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, Request, HTTPException

from core.config import get_settings
from models.models import *

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self):
        self.pwd_context = pwd_context

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> str:
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encode_jwt = jwt.encode(to_encode, settings.secret_token, settings.algorithm)
        return encode_jwt

    def get_token(request: Request):
        token = request.cookies.get("user_access_token")
        if not token:
            raise HTTPException(status_code=401, detail="Token not found")

        return token

    def verify_token(token: str = Depends(get_token)):
        try:
            payload = jwt.decode(token, settings.secret_token, settings.algorithm)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        expire = payload.get("exp")
        expire_time = datetime.fromtimestamp(int(expire), tz=timezone.utc)

        if not expire or expire_time < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Token expired")

        user = payload.get("sub")
        print(user)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user
