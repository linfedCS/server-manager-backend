from pydantic import BaseModel, Field, RootModel, EmailStr, field_validator
from typing import Any, Dict, List, Optional, Union
from enum import Enum


# Error class
class ErrorResponse(BaseModel):
    status: str = Field(None)
    msg: str


class ServerOnline(BaseModel):
    status: str = Field("online")
    server_id: int
    name: str
    ip: str
    port: int
    map_id: int
    players_current: int
    players_max: int


class ServerOffline(BaseModel):
    status: str = Field("offline")
    server_id: int
    name: str


class ServerResponse(RootModel):
    root: List[Union[ServerOnline, ServerOffline]]


class MapItem(BaseModel):
    name: str
    map_id: int


class MapsResponse(BaseModel):
    item: List[MapItem]


class ServerRequest(BaseModel):
    server_id: int


class ServerStartResponse(BaseModel):
    status: str
    data: ServerOnline


class ServerStopResponse(BaseModel):
    status: str
    data: ServerOffline


class ServerSettingsRequest(BaseModel):
    server_id: int
    map_change: Optional[int] = Field(
        None, description="Paste map_id from /maps", alias="map_id"
    )


class MapChangeResponse(BaseModel):
    status: str
    msg: str


class SettingsResponse(BaseModel):
    map_change: Optional[MapChangeResponse]


class ServerSettingsResponse(BaseModel):
    data: SettingsResponse


# TS3 server settings
class Ts3NewChannelRequest(BaseModel):
    channel_name: str
    channel_pass: Optional[str] = Field(None)


class Ts3NewChannelResponse(BaseModel):
    status: str
    msg: str


class Ts3Monitoring(BaseModel):
    channel_name: str
    total_clients: int
    client_nickname: list[str]


class Ts3MonitoringResponse(BaseModel):
    data: list[Ts3Monitoring]


# Auth
class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: EmailStr = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

class UserCreateResponse(BaseModel):
    status: str
    msg: str


class UserAuthenticatedResponse(BaseModel):
    status: str
    msg: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    detail: list[ErrorResponse]

# Decorators for settings
class SettingsDispatcher:
    def __init__(self):
        self.handlers = {}

    def register(self, field_name: str):
        def decorator(handler):
            self.handlers[field_name] = handler
            return handler

        return decorator

    async def handle(self, data: Dict[str, Any]):
        result = {}

        for field, handler in self.handlers.items():
            if field in data and field != "server_id":
                result[field] = await handler(data)
        return result
