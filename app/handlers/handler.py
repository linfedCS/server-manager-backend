import asyncio
from typing import Any, Dict
from dotenv import load_dotenv
from models.models import *
import os
import aiohttp
import asyncssh

load_dotenv()
HOST_URL = os.getenv("HOST_URL")

SSH_HOST = os.getenv("HOST_IP")
SSH_USER = os.getenv("SSH_USER")
SSH_PRIVATE_KEY = os.getenv("SSH_KEY")
if SSH_PRIVATE_KEY is not None:
    key = SSH_PRIVATE_KEY.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)

dispatcher = SettingsDispatcher()


@dispatcher.register("map_change")
async def handler_map(data: Dict[int, Any]):
    try:
        server_id = data["server_id"]
        map_id = data["map_change"]

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HOST_URL}/api/maps") as map_response, \
                    session.get(f"{HOST_URL}/api/servers") as servers_response:
                        maps = await map_response.json()
                        servers = await servers_response.json()

        map_dict = {item["map_id"]: item["name"] for item in maps}
        map_name = map_dict.get(map_id)

        server = next((s for s in servers if s.get("server_id") == server_id), None)

        if not server:
            return ErrorResponse(status="error", msg="Server not found").model_dump()

        if server.get("map_id") == map_id:
            return MapChangeResponse(status="failed", msg="Map already sets")

        async with asyncssh.connect(
            SSH_HOST, username=SSH_USER, client_keys=["ssh_key"], known_hosts=None
        ) as ssh:
            command = f"cs2-server @prac{server_id} exec map {map_name}"
            result = await ssh.run(command)

            if result.stderr:
                return ErrorResponse(status="error", msg="SSH error").model_dump()

        async with aiohttp.ClientSession() as session:
            await asyncio.sleep(2)
            async with session.get(f"{HOST_URL}/api/servers", timeout=5) as response:
                servers = await response.json()
                if server_update := next(
                    (s for s in servers if s.get("server_id") == server_id), None
                ):
                    if server_update["map_id"] != map_id:
                        return MapChangeResponse(
                            status="failed", msg="Map has not been changed"
                        )
                    return MapChangeResponse(
                        status="success", msg="Map has been changed"
                    )

    except aiohttp.ClientError as e:
        return ErrorResponse(status="error", msg="API request error").model_dump()
    except asyncssh.Error as e:
        return ErrorResponse(status="error", msg="SSH connection error").model_dump()
    except KeyError as e:
        return ErrorResponse(status="error", msg="Missing required field").model_dump()
    except Exception as e:
        return ErrorResponse(status="error", msg="Unexpected error").model_dump()
