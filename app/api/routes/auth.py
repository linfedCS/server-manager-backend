from fastapi import APIRouter, Response, Depends
from services.user_service import UserService
from services.auth_service import AuthService
from models.models import *

router = APIRouter()
user_service = UserService()
auth_service = AuthService()

@router.post("/register")
async def register(user_create: UserCreate):
    return user_service.register_user(user_create)

@router.post("/login")
async def login(login_user: LoginRequest, response: Response):
    return user_service.authenticate_user(login_user, response)

@router.get("/user")
async def get_user(user = Depends(user_service.get_user)):
    return user

@router.post("/logout")
async def logout_user(response: Response):
    response.delete_cookie(key="user_access_token")
    return {"msg": "Logout success"}
