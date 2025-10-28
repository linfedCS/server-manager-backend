from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException

from core.config import get_settings
from models.models import ErrorResponse

import aiohttp


settings = get_settings()


class SteamService:
    async def get_srcds_token(self, server_name):
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    "key": settings.steam_web_api_key,
                    "appid": 730,
                    "memo": server_name,
                }
                async with session.post(
                    "https://api.steampowered.com/IGameServersService/CreateAccount/v1/",
                    params=params,
                ) as response:
                    response.raise_for_status()

                    result = await response.json()

                    server_steamid = result["response"]["steamid"]
                    srcd_token = result["response"]["login_token"]

                    return server_steamid, srcd_token

            except aiohttp.ClientResponseError as e:
                error_response = jsonable_encoder(
                    ErrorResponse(status=f"HTTP error: {e.status} - {e.message}")
                )
                raise HTTPException(status_code=..., detail=error_response)
            except aiohttp.ClientError as e:
                error_response = jsonable_encoder(
                    ErrorResponse(status=f"Network error: {e}")
                )
                raise HTTPException(status_code=..., detail=error_response)
            except Exception as e:
                error_response = jsonable_encoder(
                    ErrorResponse(status=f"Unexpected error: {e}")
                )
                raise HTTPException(status_code=..., detail=error_response)

    async def delete_srcds_token(self, server_steamid):
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    "key": settings.steam_web_api_key,
                    "steamid": server_steamid
                }

                async with session.post("https://api.steampowered.com/IGameServersService/DeleteAccount/v1/", params=params) as response:
                    response.raise_for_status()

                    result = await response.json()

                    return result

            except aiohttp.ClientResponseError as e:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg=f"HTTP error: {e.status} - {e.message}")
                )
                raise HTTPException(status_code=..., detail=error_response)
            except aiohttp.ClientError as e:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg=f"Network error: {e}")
                )
                raise HTTPException(status_code=520, detail=error_response)
            except Exception as e:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg=f"Unexpected error: {e}")
                )
                raise HTTPException(status_code=520, detail=error_response)
