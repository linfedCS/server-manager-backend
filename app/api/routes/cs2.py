from fastapi import APIRouter
from services.cs2_service import CS2Service
from models.models import *

router = APIRouter()
cs2_service = CS2Service()

@router.get(
    "/servers",
    response_model=ServerResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def list_servers():
    return await cs2_service.list_servers()

@router.get(
    "/maps",
    response_model=List[MapItem],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    }
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
    }
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
    }
)
async def stop_server(request: ServerRequest):
    return await cs2_service.stop_server(request)

@router.post(
    "/server/settings",
    response_model=ServerSettingsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def execute_commands(request: ServerSettingsRequest):
    return cs2_service.execute_commands(request)
