from fastapi import HTTPException, Response, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.encoders import jsonable_encoder

from db.database import get_db_connection
from models.models import *
from services.auth_service import AuthService
from services.email_service import send_verification_email
from core.config import Settings

settings = Settings()
auth_service = AuthService()


class UserService:
    def register_user(
        self,
        background_task: BackgroundTasks,
        user_create: UserCreate,
        role: UserRole = UserRole.USER,
        is_verified: bool = False,
    ):
        username_form_db = self._get_username_from_db(user_create.username)
        email_from_db = self._get_email_from_db(user_create.email)

        if username_form_db is not None:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Username already exists")
            )
            raise HTTPException(status_code=404, detail=error_response)

        if email_from_db is not None:
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Email already exists")
            )
            raise HTTPException(status_code=404, detail=error_response)

        hashed_password = auth_service.get_password_hash(user_create.password)

        self._insert_users_into_db(
            username=user_create.username,
            hashed_password=hashed_password,
            email=user_create.email,
            role=role,
            is_verified=is_verified,
        )

        background_task.add_task(send_verification_email, user_create.email)

        return UserCreateResponse(
            status="success",
            msg="User registered successfully. Please verify your email",
        )

    def authenticate_user(self, login_user: LoginRequest, response: Response):
        user_data_form_db = self._get_users_data(login_user.username)

        user_data = user_data_form_db[0] if user_data_form_db else None

        if not user_data or not auth_service.verify_password(
            login_user.password, user_data.get("hashed_password")
        ):
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Incorrect username or password")
            )
            raise HTTPException(status_code=401, detail=error_response)

        is_disable_db = self._get_user_is_disable(login_user.username)
        is_disable = str(is_disable_db).strip("()").replace(",", "")
        print(is_disable)
        if is_disable == "True":
            error_response = jsonable_encoder(
                ErrorResponse(status="failed", msg="Please verified your email")
            )
            raise HTTPException(status_code=403, detail=error_response)

        token_data = {"sub": user_data["username"], "role": user_data["role"]}
        access_token = auth_service.create_access_token(data=token_data)
        refresh_token = auth_service.create_refresh_token(data=token_data)

        self._update_refresh_token_into_db(
            username=user_data["username"], refresh_token=refresh_token
        )

        response.set_cookie(
            key="user_access_token",
            value=access_token,
            httponly=True,
            max_age=settings.access_token_expire_minutes * 60,
        )
        response.set_cookie(
            key="user_refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        )

        return UserAuthenticatedResponse(status="success", msg="You are authenticated")

    def verify_email(self, token):
        try:
            email = auth_service.verify_email_token(token)

            if not email:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg="Invalid token")
                )
                raise HTTPException(status_code=400, detail=error_response)

            user = self._get_email_from_db(email)
            if user is None:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg="User not found")
                )
                raise HTTPException(status_code=404, detail=error_response)

            is_verified_db = self._get_is_verified_email(email)
            is_verified = str(is_verified_db).strip("()").replace(",", "")
            if is_verified == "True":
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg="Email is verified")
                )
                raise HTTPException(status_code=409, detail=error_response)

            self._update_is_verified_email(email)
            self._update_user_is_disable(value=False, user=email)

            return RedirectResponse(url="https://dev.linfed.ru")

        except HTTPException:
            raise


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
                cur.execute("SELECT email FROM users WHERE email = %s", (email,))
                result = cur.fetchall()

                return result[0] if result else None

    def _get_users_data(self, username):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                users = cur.fetchall()
                users_columns = [desc[0] for desc in cur.description]
                users_data = [dict(zip(users_columns, row)) for row in users]

                return users_data

    def _get_is_verified_email(self, email):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_verified FROM users WHERE email = %s", (email,))
                result = cur.fetchall()

                return result[0] if result else None

    def _get_user_is_disable(self, user):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_disable FROM users WHERE username = %s OR email = %s",
                    (user, user),
                )
                result = cur.fetchall()

                return result[0] if result else None

    def _insert_users_into_db(
        self, username, hashed_password, email, role, is_verified
    ):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, email, hashed_password, role, is_verified) VALUES (%s, %s, %s, %s, %s)",
                    (username, email, hashed_password, role, is_verified),
                )

    def _update_refresh_token_into_db(self, username, refresh_token):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET refresh_token = %s WHERE username = %s",
                    (refresh_token, username),
                )

    def _update_is_verified_email(sefl, email):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_verified = TRUE WHERE email = %s", (email,)
                )

    def _update_user_is_disable(self, value, user):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_disable = %s WHERE username = %s OR email = %s",
                    (value, user, user),
                )
