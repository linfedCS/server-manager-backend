from fastapi import APIRouter
from services.user_service import UserService
from models.models import *

router = APIRouter()
user_service = UserService()

@router.post("/register")
async def register(user_create: UserCreate):
    return user_service.register_user(user_create)

@router.post("/login")
async def login(login_user: LoginRequest):
    return user_service.authenticate_user(login_user)
