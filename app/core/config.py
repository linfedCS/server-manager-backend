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

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
