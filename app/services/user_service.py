from fastapi import HTTPException, Response
from fastapi.encoders import jsonable_encoder


from db.database import get_db_connection
from models.models import *
from services.auth_service import AuthService
from core.config import Settings

settings = Settings()
auth_service = AuthService()


class UserService:
    def register_user(self, user_create: UserCreate, role: UserRole = UserRole.USER):
        username_form_db = self._get_username_from_db(user_create.username)
        email_from_db = self._get_email_from_db(user_create.email)

        if username_form_db is not None:
            return ErrorResponse(status="failed", msg="Username already exists")

        if email_from_db is not None:
            return ErrorResponse(status="failed", msg="Email already exists")

        hashed_password = auth_service.get_password_hash(user_create.password)

        self._insert_users_into_db(
            username=user_create.username, hashed_password=hashed_password, email=user_create.email, role=role
        )
        return UserCreateResponse(status="Success", msg="User registered successfully")

    def authenticate_user(self, login_user: LoginRequest, response: Response):
        user_data_form_db = self._get_users_data(login_user.username)

        user_data = user_data_form_db[0] if user_data_form_db else None

        if not user_data or not auth_service.verify_password(login_user.password, user_data.get("hashed_password")):
            raise HTTPException(status_code=401, detail="Incorrect username or password")


        token_data = {"sub": user_data["username"], "role": user_data["role"]}
        access_token = auth_service.create_access_token(data=token_data)
        refresh_token = auth_service.create_refresh_token(data=token_data)

        self._insert_refresh_token_into_db(username=user_data["username"], refresh_token=refresh_token)

        response.set_cookie(
            key="user_access_token",
            value=access_token,
            httponly=True,
            max_age=settings.access_token_expire_minutes *60
        )
        response.set_cookie(
            key="user_refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60
        )

        return {
            "acces_token": access_token,
            "refresh_token": refresh_token
        }

    # def get_user(self, username: str = Depends(auth_service.verify_token)):
    #     user = self._get_users_data(username)
    #     if not user:
    #         raise HTTPException(status_code=404, detail="User not found")

    #     return user

    def _get_username_from_db(self, username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username FROM users WHERE username = %s", (username,)
                )
                result = cur.fetchall()

                return result[0] if result else None

    def _get_email_from_db(self, email):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT email FROM users WHERE email = %s", (email,)
                )
                result = cur.fetchall()

                return result[0] if result else None

    def _insert_users_into_db(self, username, hashed_password, email, role):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, email, hashed_password, role) VALUES (%s, %s, %s, %s)",
                    (username, email, hashed_password, role),
                )

    def _insert_refresh_token_into_db(self, username, refresh_token):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET refresh_token = %s WHERE username = %s",
                    (refresh_token, username)
                )

    def _get_users_data(self, username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                users = cur.fetchall()
                users_columns = [desc[0] for desc in cur.description]
                users_data = [dict(zip(users_columns, row)) for row in users]

                return users_data
