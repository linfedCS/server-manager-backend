from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import Optional
from jose import jwt, JWTError

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
        expire = datetime.now(timezone.utc) + timedelta(days=30)
        to_encode.update({"exp": expire})
        encode_jwt = jwt.encode(to_encode, settings.secret_token, settings.algorithm)
        return encode_jwt

    def verify_token(self, token: str) -> Optional[TokenData]:
        try:
            payload = jwt.decode(
                token, settings.secret_token, algorithms=settings.algorithm
            )
            username: str = payload.get("sub")
            role: str = payload.get("role", UserRole.USER)

            if username is None:
                return None

            return TokenData(username=username, role=UserRole(role))

        except (JWTError, ValueError):
            return None
