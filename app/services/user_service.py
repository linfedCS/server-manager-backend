from fastapi import HTTPException, Request, Depends

from db.database import get_db_connection
from models.models import *
from services.auth_service import AuthService
from core.config import Settings

settings = Settings()
auth_service = AuthService()

class UserService:
    def register_user(self, user_create: UserCreate, role: UserRole = UserRole.USER):
        username = user_create.username
        username_form_db = self._get_username_from_db(username)

        if username_form_db is not None:
            return ErrorResponse(status="failed", msg="Username already exists")

        hashed_password = auth_service.get_password_hash(user_create.password)

        self._insert_users_into_db(username=username, hashed_password=hashed_password, email=user_create.email)
        return UserCreateResponse(status="Success", msg="User registered successfully")

    def authenticate_user(self, login_user: LoginRequest, response):
        user = login_user.username
        user_data_form_db = self._get_users_data(user)

        user_data = None
        for item in user_data_form_db:
            user_data = item
            break

        if not user_data or not user_data["username"] or not auth_service.verify_password(login_user.password, user_data.get("hashed_password")):
            return ErrorResponse(status="failed", msg="Incorrect username or password")

        access_token = auth_service.create_access_token(data={"sub": user_data["username"], "role": user_data["role"]})
        response.set_cookie(key="user_access_token", value=access_token, httponly=True)

        return {"access_token": access_token, "refresh_token": None}


    def get_user(self, username: str = Depends(auth_service.verify_token)):
        user = self._get_users_data(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user



    def _get_username_from_db(self, username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT username FROM users WHERE username = %s", (username,))
                result = cur.fetchall()

                return result[0] if result else None

    def _insert_users_into_db(self, username, hashed_password, email):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, email, hashed_password) VALUES (%s, %s, %s)",
                    (username, email, hashed_password)
                )

    def _get_users_data(self, username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                users = cur.fetchall()
                users_columns = [desc[0] for desc in cur.description]
                users_data = [dict(zip(users_columns, row)) for row in users]

                return users_data
