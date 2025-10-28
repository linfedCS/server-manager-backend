from pydantic_settings import BaseSettings
from typing import Optional

import os

class Settings(BaseSettings):
    host_url: str = os.getenv("HOST_URL", "")
    host: str = os.getenv("HOST", "")

    #TS3 Settings Connection
    ts3_host: str = os.getenv("TS3_HOST", "")
    ts3_port: int = os.getenv("TS3_PORT", "")
    ts3_user: str = os.getenv("TS3_USER", "")
    ts3_pass: str = os.getenv("TS3_PASS", "")

    #SSH Settings Connection
    ssh_host: str = os.getenv("SSH_HOST", "")
    ssh_user: str = os.getenv("SSH_USER", "")
    ssh_key: Optional[str] = os.getenv("SSH_KEY", "")

    #DB Settings Connection
    db_name: str = os.getenv("DB_NAME", "")
    db_user: str = os.getenv("DB_USER", "")
    db_pass: str = os.getenv("DB_PASSWORD", "")
    db_host: str = os.getenv("DB_HOST", "")
    db_port: int = os.getenv("DB_PORT", "")

    #Auth
    secret_token: str = os.getenv("SECRET_TOKEN", "")
    algorithm: str = os.getenv("ALGORITHM", "")
    access_token_expire_minutes: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "")
    refresh_token_expire_days: int = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "")
    email_token_expire_minutes: int = os.getenv("EMAIL_TOKEN_EXPIRE_MINUTES", "")

    #Email
    mail_username: str = os.getenv("MAIL_USERNAME", "")
    mail_password: str = os.getenv("MAIL_PASSWORD", "")
    mail_from: str = os.getenv("MAIL_FROM", "")
    mail_port: int = os.getenv("MAIL_PORT", "")
    mail_server: str = os.getenv("MAIL_SERVER", "")
    mail_starttls: bool = os.getenv("MAIL_STARTTLS", "")
    mail_ssl_tls: bool = os.getenv("MAIL_SSL_TLS", "")

    #RCON
    rcon_password: str = os.getenv("RCON_PASSWORD", "")

    #Steam
    steam_web_api_key: str = os.getenv("STEAM_WEB_API_KEY", "")

    #Docs
    docs_admin_username: str = os.getenv("ADMIN_USERNAME", "")
    docs_admin_password: str = os.getenv("ADMIN_PASSWORD", "")

    #Monitoring server activity
    max_empty_minute: int = os.getenv("MAX_EMPTY_MINUTE", "")

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
