from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from datetime import datetime

from db.database import get_db_connection
from handlers.handler import dispatcher
from core.config import get_settings
from services.port_service import PortManager
from models.models import *

import asyncio
import a2s
import aiohttp
import asyncssh

settings = get_settings()
docker_port = PortManager()


class CS2Service:
    async def list_servers(self):
        try:
            servers, maps = self._fetch_servers_and_maps()
            map_name_to_id = {map_item["name"]: map_item["map_id"] for map_item in maps}

            results = await asyncio.gather(
                *(
                    self._check_server_status(server, map_name_to_id)
                    for server in servers
                )
            )
            return results

        except Exception as e:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg=f"Internal server error: {e}")
            )
            return JSONResponse(status_code=500, content=error_response)

    async def list_server_by_owner(self, owner: UserPayload):
        try:
            servers, maps = self._fetch_servers_by_owner(owner=owner.username)
            map_name_to_id = {map_item["name"]: map_item["map_id"] for map_item in maps}

            result = await asyncio.gather(
                *(
                    self._check_server_status(server, map_name_to_id)
                    for server in servers
                )
            )
            return result

        except Exception as e:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg=f"Internal server error: {e}")
            )
            return JSONResponse(status_code=500, content=error_response)

    async def list_maps(self):
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name, map_id FROM maps")
                    maps = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    maps_list = [dict(zip(columns, row)) for row in maps]

                    map_items = [MapItem(**map_dict) for map_dict in maps_list]
                    return map_items

        except Exception:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg="Internal server error")
            )
            return JSONResponse(status_code=500, content=error_response)

    async def create_server(self, request: CreateServerRequest, owner: UserPayload):

        try:
            port = docker_port.get_free_port()
            async with asyncssh.connect(
                settings.ssh_host,
                username=settings.ssh_user,
                client_keys=["ssh_key"],
                known_hosts=None,
            ) as ssh:
                command = f"""docker run -dit --name={request.name} \
                -e SRCDS_TOKEN="59ACFD1ADF90380EC352C01FD4F48279" \
                -e CS2_CFG_URL="https://file.linfed.ru/cs2.zip" \
                -v /home/cs/cs2-docker:/home/steam/cs2-dedicated \
                -p {port}:27015/tcp -p {port}:27015/udp \
                joedwards32/cs2"""

                result = await ssh.run(command)
                if result.stderr:
                    error_response = jsonable_encoder(
                        ErrorResponse(status="error", msg="SSH Error")
                    )
                    return JSONResponse(status_code=500, content=error_response)

                self._insert_server_into_db(
                    port=port, name=request.name, owner=owner.username
                )

                timeout_seconds = 60
                check_interval = 1
                start_time = datetime.now()

                async with aiohttp.ClientSession() as session:
                    while (datetime.now() - start_time).seconds < timeout_seconds:
                        try:
                            async with session.get(
                                f"{settings.host_url}/api/cs2/servers", timeout=5
                            ) as response:
                                servers = await response.json()
                                server = next(
                                    (
                                        s
                                        for s in servers
                                        if s.get("name") == request.name
                                    ),
                                    None,
                                )
                                if not server:
                                    error_response = jsonable_encoder(
                                        ErrorResponse(
                                            status="error", msg="Server not found"
                                        )
                                    )
                                    return JSONResponse(
                                        status_code=400, content=error_response
                                    )

                                if server.get("status") == "online":
                                    server_data = ServerOnline(**server)

                                    occupy_port = docker_port.occupy_port(
                                        port=port, container_name=request.name
                                    )
                                    if not occupy_port:
                                        await docker_port.release_port(request.name)
                                        error_response = jsonable_encoder(
                                            ErrorResponse(
                                                status="failed",
                                                msg="Failed to occupy port",
                                            )
                                        )
                                        return JSONResponse(
                                            status_code=500, content=error_response
                                        )

                                    asyncio.create_task(
                                        self._monitoring_server_activity(request.name)
                                    )

                                    return ServerStartResponse(
                                        status="success", data=server_data
                                    )

                                await asyncio.sleep(check_interval)
                                continue

                        except (aiohttp.ClientError, asyncio.TimeoutError):
                            await asyncio.sleep(check_interval)
                            continue

                    await self._delete_server_container(request.name)
                    error_response = jsonable_encoder(
                        ErrorResponse(
                            status="failed",
                            msg="Request Timeout - server didn't start",
                        )
                    )
                    return JSONResponse(status_code=408, content=error_response)

        except asyncssh.Error as e:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg=f"SSH connection error: {str(e)}")
            )
            return JSONResponse(status_code=500, content=error_response)

    async def start_server(self, request: ServerRequest):
        server_id = request.server_id

        if not server_id:
            error_response = jsonable_encoder(
                ErrorResponse(
                    status="failed", msg="Validation Error - check server_id params"
                )
            )
            return JSONResponse(status_code=422, content=error_response)

        try:
            async with asyncssh.connect(
                settings.ssh_host,
                username=settings.ssh_user,
                client_keys=["ssh_key"],
                known_hosts=None,
            ) as ssh:
                result = await ssh.run(f"cs2-server @prac{server_id} start")

                if result.stderr:
                    error_response = jsonable_encoder(
                        ErrorResponse(status="error", msg="SSH Error")
                    )
                    return JSONResponse(status_code=500, content=error_response)

                timeout_seconds = 60
                check_interval = 1
                start_time = datetime.now()

                async with aiohttp.ClientSession() as session:
                    while (datetime.now() - start_time).seconds < timeout_seconds:
                        try:
                            async with session.get(
                                f"{settings.host_url}/api/servers", timeout=5
                            ) as response:
                                servers = await response.json()
                                server = next(
                                    (
                                        s
                                        for s in servers
                                        if s.get("server_id") == server_id
                                    ),
                                    None,
                                )
                                if not server:
                                    error_response = jsonable_encoder(
                                        ErrorResponse(
                                            status="error", msg="Server not found"
                                        )
                                    )
                                    return JSONResponse(
                                        status_code=400, content=error_response
                                    )

                                if server.get("status") == "online":
                                    server_data = ServerOnline(**server)
                                    return ServerStartResponse(
                                        status="success", data=server_data
                                    )

                                await asyncio.sleep(check_interval)
                                continue

                        except (aiohttp.ClientError, asyncio.TimeoutError):
                            await asyncio.sleep(check_interval)
                            continue

                    error_response = jsonable_encoder(
                        ErrorResponse(
                            status="failed",
                            msg="Request Timeout - server didn't start",
                        )
                    )
                    return JSONResponse(status_code=408, content=error_response)

        except asyncssh.Error as e:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg=f"SSH connection error: {str(e)}")
            )
            return JSONResponse(status_code=500, content=error_response)

    async def stop_server(self, request: ServerRequest):
        server_id = request.server_id

        if not server_id:
            error_response = jsonable_encoder(
                ErrorResponse(
                    status="error", msg="Validation Error - check server_id params"
                )
            )
            return JSONResponse(status_code=422, content=error_response)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{settings.host_url}/api/servers", timeout=5
                ) as response:
                    servers = await response.json()
                    server = next(
                        (s for s in servers if s.get("server_id") == server_id), None
                    )
                    if not server:
                        error_response = jsonable_encoder(
                            ErrorResponse(status="error", msg="Server not found")
                        )
                        return JSONResponse(
                            status_code=400,
                            content=error_response,
                        )
                    if server.get("players_current") >= 1:
                        error_response = jsonable_encoder(
                            ErrorResponse(
                                status="failed",
                                msg="You can't stop the server while there are players on it",
                            )
                        )
                        return JSONResponse(status_code=409, content=error_response)

        except aiohttp.ClientError:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg="Couldn't check server status")
            )
            return JSONResponse(status_code=500, content=error_response)

        try:
            async with asyncssh.connect(
                settings.ssh_host,
                username=settings.ssh_user,
                client_keys=["ssh_key"],
                known_hosts=None,
            ) as ssh:
                result = await ssh.run(f"cs2-server @prac{server_id} stop")

                if result.stderr:
                    error_response = jsonable_encoder(
                        ErrorResponse(status="error", msg="SSH Error")
                    )
                    return JSONResponse(status_code=500, content=error_response)

                timeout_seconds = 60
                check_interval = 1
                start_time = datetime.now()

                async with aiohttp.ClientSession() as session:
                    while (datetime.now() - start_time).seconds < timeout_seconds:
                        try:
                            async with session.get(
                                f"{settings.host_url}/api/servers", timeout=5
                            ) as response:
                                servers = await response.json()

                                if server := next(
                                    (
                                        s
                                        for s in servers
                                        if s.get("server_id") == server_id
                                    ),
                                    None,
                                ):
                                    if not server:
                                        error_response = jsonable_encoder(
                                            ErrorResponse(
                                                status="error", msg="Server not found"
                                            )
                                        )
                                        return JSONResponse(
                                            status_code=400,
                                            content=error_response,
                                        )

                                    if server.get("status") == "offline":
                                        server_data = ServerOffline(**server)
                                        return ServerStopResponse(
                                            status="success", data=server_data
                                        )

                                    await asyncio.sleep(check_interval)
                                    continue

                        except (aiohttp.ClientError, asyncio.TimeoutError):
                            await asyncio.sleep(check_interval)
                            continue

                    error_response = jsonable_encoder(
                        ErrorResponse(
                            status="failed", msg="Request Timeout - server didn't stop"
                        )
                    )
                    return JSONResponse(status_code=408, content=error_response)

        except asyncssh.Error as e:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg="SSH connection error")
            )
            return JSONResponse(status_code=500, content=error_response)

    async def execute_commands(self, request: ServerSettingsRequest):
        try:
            data = request.model_dump(exclude_unset=True)

            fields_provided = set(data.keys()) - {"server_id"}
            if not fields_provided:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg="No one settings have been sent")
                )
                return JSONResponse(status_code=400, content=error_response)

            result = await dispatcher.handle(data)

            if not result:
                error_response = jsonable_encoder(
                    ErrorResponse(status="failed", msg="Check settings params")
                )
                return JSONResponse(status_code=400, content=error_response)

            error_field = None
            error_data = None

            for field_name, field_value in result.items():
                if isinstance(field_value, dict) and field_value.get("status") in [
                    "error",
                    "failed",
                ]:
                    error_field = field_name
                    error_data = field_value
                    break

            if error_field:
                status_code = 500 if error_data.get("status") == "error" else 400
                return JSONResponse(status_code=status_code, content=error_data)

            settings_response = SettingsResponse(**result)
            response = ServerSettingsResponse(data=settings_response)

            return response

        except Exception as e:
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg=f"Internal server error {e}")
            )
            return JSONResponse(status_code=500, content=error_response)

    def _fetch_servers_and_maps(self):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM servers")
                servers = cur.fetchall()
                servers_columns = [desc[0] for desc in cur.description]
                server_list = [dict(zip(servers_columns, row)) for row in servers]

                cur.execute("SELECT name, map_id FROM maps")
                maps = cur.fetchall()
                maps_columns = [desc[0] for desc in cur.description]
                maps_list = [dict(zip(maps_columns, row)) for row in maps]

                return server_list, maps_list

    def _fetch_servers_by_owner(self, owner):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM servers WHERE owner = %s", (owner,))
                servers = cur.fetchall()
                servers_colums = [desc[0] for desc in cur.description]
                server_list = [dict(zip(servers_colums, row)) for row in servers]

                cur.execute("SELECT name, map_id FROM maps")
                maps = cur.fetchall()
                maps_colums = [desc[0] for desc in cur.description]
                maps_list = [dict(zip(maps_colums, row)) for row in maps]

                return server_list, maps_list

    def _insert_server_into_db(self, name, port, owner):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO servers (name, port, owner) VALUES (%s, %s, %s)",
                    (name, port, owner),
                )

    def _delete_server_from_db(sefl, server_name: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM servers WHERE name = %s", (server_name,))

    async def _check_server_status(self, server, map_name_to_id):
        try:
            address = (server["ip"], server["port"])
            info = await a2s.ainfo(address)
            map_id = map_name_to_id.get(info.map_name)

            return ServerOnline(
                status="online",
                # server_id=server["server_id"],
                name=server["name"],
                ip=server["ip"],
                port=server["port"],
                map_id=map_id,
                players_current=int(info.player_count),
                players_max=info.max_players,
            )

        except Exception as e:
            return ServerOffline(
                status="offline",
                # server_id=server["server_id"],
                name=server["name"],
            )

    async def _monitoring_server_activity(self, server_name: str):
        empty_minute = 0
        max_empty_minute = 5

        async with aiohttp.ClientSession() as session:
            while empty_minute < max_empty_minute:
                await asyncio.sleep(60)

                try:
                    async with session.get(
                        f"{settings.host_url}/api/cs2/servers", timeout=5
                    ) as response:
                        servers = await response.json()
                        server = next(
                            (s for s in servers if s.get("name") == server_name),
                            None,
                        )

                        if not server:
                            return

                        players_current = server.get("players_current")

                        if players_current == 0:
                            empty_minute += 1
                        else:
                            if empty_minute > 0:
                                empty_minute = 0

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    continue

        await self._delete_server_container(server_name)

    async def _delete_server_container(self, server_name: str):
        try:
            async with asyncssh.connect(
                settings.ssh_host,
                username=settings.ssh_user,
                client_keys=["ssh_key"],
                known_hosts=None,
            ) as ssh:
                stop_command = f"docker stop {server_name}"
                await ssh.run(stop_command)

                rm_command = f"docker rm {server_name}"
                result = await ssh.run(rm_command)

                if result.stderr:
                    return False

                docker_port.release_port(server_name)
                self._delete_server_from_db(server_name)

                return True
        except asyncssh.Error as e:
            return False
