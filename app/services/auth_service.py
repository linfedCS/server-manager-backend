from fastapi import Depends, Request, Response, HTTPException
from datetime import datetime, timedelta, timezone
from fastapi.encoders import jsonable_encoder
from passlib.context import CryptContext
from jose import jwt, JWTError

from db.database import get_db_connection
from core.config import get_settings
from models.models import *


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


class AuthService:
    def __init__(self):
        self.pwd_context = pwd_context

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> str:
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        to_encode.update({"exp": expire, "type": "access"})
        encode_jwt = jwt.encode(to_encode, settings.secret_token, settings.algorithm)
        return encode_jwt

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        to_encode.update({"exp": expire, "type": "refresh"})
        encode_jwt = jwt.encode(to_encode, settings.secret_token, settings.algorithm)
        return encode_jwt

    def create_email_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.email_token_expire_minutes
        )
        to_encode.update({"exp": expire, "type": "email"})
        encode_jwt = jwt.encode(to_encode, settings.secret_token, settings.algorithm)
        return encode_jwt

    def get_access_token(request: Request):
        token = request.cookies.get("user_access_token")
        if not token:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Access token not found")
            )
            raise HTTPException(status_code=401, detail=error_response)
        return token

    def get_refresh_token(request: Request):
        token = request.cookies.get("user_refresh_token")
        if not token:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Refresh token not found")
            )
            raise HTTPException(status_code=401, detail=error_response)
        return token

    def verify_access_token(self, token: str = Depends(get_access_token)):
        try:
            payload = jwt.decode(token, settings.secret_token, settings.algorithm)
        except JWTError:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Invalid access token")
            )
            raise HTTPException(status_code=401, detail=error_response)

        if payload.get("type") != "access":
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Invalid access token")
            )
            raise HTTPException(status_code=401, detail=error_response)

        user = payload.get("sub")
        if not user:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="User not found")
            )
            raise HTTPException(status_code=404, detail=error_response)
        return user

    def verify_refresh_token(self, token: str = Depends(get_refresh_token)):
        try:
            payload = jwt.decode(token, settings.secret_token, settings.algorithm)
        except JWTError:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Invalid refresh token")
            )
            raise HTTPException(status_code=400, detail=error_response)

        user = payload.get("sub")
        if not user:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="User not found")
            )
            raise HTTPException(status_code=404, detail=error_response)

        refresh_token_from_db = self._get_refresh_token_from_db(user)
        clean_refresh_token = (
            str(refresh_token_from_db).strip("()").replace("'", "").replace(",", "")
        )
        if clean_refresh_token != token:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Invalid refresh token")
            )
            raise HTTPException(status_code=401, detail=error_response)

        if payload.get("type") != "refresh":
            error_response = jsonable_encoder(
                ErrorResponse(
                    status="failed", msg="Token type mismatch: expected refresh token"
                )
            )
            raise HTTPException(status_code=401, detail=error_response)
        return user

    def verify_email_token(self, token: str):
        try:
            payload = jwt.decode(token, settings.secret_token, settings.algorithm)
            email: str = payload.get("sub")

            if email is None:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg="Invalid token")
                )
                raise HTTPException(status_code=400, detail=error_response)

            return email
        except JWTError:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Invalid token")
            )
            raise HTTPException(status_code=400, detail=error_response)

    def refresh_token(self, response: Response, current_user: str):
        token_data = {"sub": current_user}

        new_access_token = self.create_access_token(data=token_data)
        new_refresh_token = self.create_refresh_token(data=token_data)

        self._insert_refresh_token_into_db(
            username=current_user, refresh_token=new_refresh_token
        )

        response.set_cookie(
            key="user_access_token",
            value=new_access_token,
            httponly=True,
            max_age=settings.access_token_expire_minutes * 60,
        )
        response.set_cookie(
            key="user_refresh_token",
            value=new_refresh_token,
            httponly=True,
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        )

        return {"access_token": new_access_token, "refresh_token": new_refresh_token}

    def get_current_user(self, request: Request) -> UserPayload:
        token = request.cookies.get("user_access_token")

        if not token:
            error_response = jsonable_encoder(ErrorResponse(status="failed", msg="Not authenticated"))
            raise HTTPException(status_code=401, detail=error_response)

        try:
            payload = jwt.decode(token, settings.secret_token, settings.algorithm)
            username = payload.get("sub")
            if username is None:
                error_response = jsonable_encoder(ErrorResponse(status="failed", msg="Invalid token"))
                raise HTTPException(status_code=401, detail=error_response)
            return UserPayload(username=username)

        except JWTError:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Invalid token")
            )
            raise HTTPException(status_code=400, detail=error_response)

    def _get_refresh_token_from_db(self, username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT refresh_token FROM users WHERE username = %s", (username,)
                )
                result = cur.fetchall()
                return result[0]

    def _insert_refresh_token_into_db(self, username, refresh_token):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET refresh_token = %s WHERE username = %s",
                    (refresh_token, username),
                )
