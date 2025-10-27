from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.encoders import jsonable_encoder

from services.cs2_service import CS2Service
from services.auth_service import AuthService
from models.models import *

router = APIRouter()
cs2_service = CS2Service()
auth_service = AuthService()


@router.get(
    "/servers",
    response_model=ServerResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_servers():
    return await cs2_service.list_servers()

@router.get("/servers/my-servers")
async def list_servers_by_owner(
    current_user: UserPayload = Depends(auth_service.get_current_user),
):
    return await cs2_service.list_server_by_owner(owner=current_user.username)


@router.get(
    "/maps",
    response_model=List[MapItem],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_maps():
    return await cs2_service.list_maps()


@router.post(
    "/server-start",
    response_model=ServerStartResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected Request"},
        408: {"model": ErrorResponse, "description": "Request Timeout"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def start_server(request: ServerRequest):
    return await cs2_service.start_server(request)


@router.post(
    "/server-stop",
    response_model=ServerStopResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected Request"},
        408: {"model": ErrorResponse, "description": "Request Timeout"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        500: {"model": ErrorResponse, "description": "Internal server Error"},
    },
)
async def stop_server(request: ServerRequest):
    return await cs2_service.stop_server(request)


@router.post(
    "/server/settings",
    response_model=ServerSettingsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def execute_commands(request: ServerSettingsRequest):
    return await cs2_service.execute_commands(request)


@router.post("/create-server")
async def create_server(
    request: CreateServerRequest,
    owner: UserPayload = Depends(auth_service.get_current_user),
):
    return await cs2_service.create_server(request=request, owner=owner)

@router.delete("/delete-server")
async def delete_server(request: DeleteServerRequest, current_user: UserPayload = Depends(auth_service.get_current_user)):
    if current_user:
        if current_user.role != "admin":
          error_response = jsonable_encoder(ErrorResponse(status="failed", msg="You don't have permissions"))
          raise HTTPException(status_code=403, detail=error_response)

        return await cs2_service._delete_server_container(server_name=request.server_name)
