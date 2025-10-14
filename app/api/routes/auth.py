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

# @router.get("/user")
# async def get_user(user = Depends(user_service.get_user)):
#     return user

@router.post("/logout")
async def logout_user(response: Response):
    response.delete_cookie(key="user_access_token")
    response.delete_cookie(key="user_refresh_token")
    return {"msg": "Logout success"}

@router.post("/refresh")
async def refresh_token(response: Response, current_user: str = Depends(auth_service.verify_refresh_token)):
    return auth_service.refresh_token(response, current_user)
