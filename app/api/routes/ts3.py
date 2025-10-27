from fastapi import APIRouter, WebSocket

from services.ts3_service import TS3Service
from models.models import *

router = APIRouter()
ts3_service = TS3Service()

@router.post(
    "/newchannel",
    response_model=Ts3NewChannelResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def ts3_new_channel(request: Ts3NewChannelRequest):
    return await ts3_service.ts3_new_channel(request)

@router.websocket(
    "/monitoring"
)
async def ts_monitoring(websocket: WebSocket):
    return await ts3_service.ts_monitoring(websocket)

@router.get("/monitoring", tags=["TS3 Handlers"], summary="WebSocket Documentation 🌐", response_model=Ts3MonitoringResponse)
async def websocket_documentation():
    """
    ## WebSocket endpoint. ##
     - #### **Protocol**: WS ####
     - #### **Path**: /api/ts3/monitoring ####
     - #### **Description**: Use this endpoint for WebSocket connection. ####
    """
    return {"message": "Этот эндпоинт предназначен для WebSocket соединения. Используйте WebSocket клиент для подключения."}
