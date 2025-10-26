from rcon.source import rcon
from dotenv import load_dotenv
from typing import Any, Dict

from core.config import get_settings
from models.models import *

import aiohttp
import asyncssh
import asyncio


load_dotenv()
settings = get_settings()


if settings.ssh_key is not None:
    key = settings.ssh_key.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)

dispatcher = SettingsDispatcher()


@dispatcher.register("map_change")
async def handler_map(data: Dict[int, Any]):
    try:
        server_name = data["server_name"]
        map_id = data["map_change"]

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.host_url}/api/cs2/maps") as map_response, \
                    session.get(f"{settings.host_url}/api/cs2/servers") as servers_response:
                        maps = await map_response.json()
                        servers = await servers_response.json()

        map_dict = {item["map_id"]: item["name"] for item in maps}
        map_name = map_dict.get(map_id)

        server = next((s for s in servers if s.get("server_name") == server_name), None)

        if not server:
            return ErrorResponse(status="error", msg="Server not found").model_dump()

        if server.get("map_id") == map_id:
            return MapChangeResponse(status="failed", msg="Map already sets")

        await rcon(f"map {map_name}", host=server["ip"], port=server["port"], passwd=settings.rcon_password)

        # async with asyncssh.connect(
        #     settings.ssh_host, username=settings.ssh_user, client_keys=["ssh_key"], known_hosts=None
        # ) as ssh:
        #     command = f"cs2-server @prac{server_name} exec map {map_name}"
        #     result = await ssh.run(command)

        #     if result.stderr:
        #         return ErrorResponse(status="error", msg="SSH error").model_dump()

        async with aiohttp.ClientSession() as session:
            await asyncio.sleep(2)
            async with session.get(f"{settings.host_url}/api/cs2/servers", timeout=5) as response:
                servers = await response.json()
                if server_update := next(
                    (s for s in servers if s.get("server_name") == server_name), None
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
