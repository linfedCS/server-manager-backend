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

    def authenticate_user(self, login_user: LoginRequest):
        user_data = login_user.username
        user_data_form_db = self._get_users_data(user_data)

        if not user_data_form_db:
            return None

        print(user_data_form_db)

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
