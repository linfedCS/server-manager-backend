from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from db.database import get_db_connection
from db.lifespan import lifespan
from handlers.handler import dispatcher
from handlers.ts3_parser import parse_channels, parse_clients
from models.models import *
import asyncio
import telnetlib3
import asyncio
import uvicorn
import os
import a2s
import aiohttp
import asyncssh


load_dotenv()

HOST_URL = os.getenv("HOST_URL")
HOST = os.getenv("HOST")

# SSH settings for ts3 server
TS3_SSH_HOST = os.getenv("TS3_SSH_HOST")
TS3_SSH_PORT = os.getenv("TS3_SSH_PORT")
TS3_SSH_USER = os.getenv("TS3_SSH_USER")
TS3_SSH_PASS = os.getenv("TS3_SSH_PASS")

# SSH settings for cs2 servers
SSH_HOST = os.getenv("HOST_IP")
SSH_USER = os.getenv("SSH_USER")
SSH_PRIVATE_KEY = os.getenv("SSH_KEY")
if SSH_PRIVATE_KEY is not None:
    key = SSH_PRIVATE_KEY.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)

app = FastAPI(
    title="Linfed | Server manager API",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    servers=[
        {"url": f"{HOST_URL}"},
    ],
    openapi_tags=[
        {"name": "CS2 Handlers", "description": ""},
        {"name": "TS3 Handlers", "description": ""},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/api/servers",
    response_model=ServerResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["CS2 Handlers"],
)
async def list_servers():
    try:

        def fetch_servers_and_maps():
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

        servers, maps = await asyncio.to_thread(fetch_servers_and_maps)

        map_name_to_id = {map_item["name"]: map_item["map_id"] for map_item in maps}

        async def check_server(server):
            try:
                address = (server["ip"], server["port"])
                info = await a2s.ainfo(address)
                map_id = map_name_to_id.get(info.map_name)

                return ServerOnline(
                    status="online",
                    server_id=server["server_id"],
                    name=server["name"],
                    ip=server["ip"],
                    port=server["port"],
                    map_id=map_id,
                    players_current=int(info.player_count),
                    players_max=info.max_players,
                )

            except Exception as e:
                return ServerOffline(
                    status="offline", server_id=server["server_id"], name=server["name"]
                )

        results = await asyncio.gather(*(check_server(server) for server in servers))
        return results

    except Exception:
        error_response = jsonable_encoder(
            ErrorResponse(status="error", msg="Internal server error")
        )
        return JSONResponse(status_code=500, content=error_response)


@app.get(
    "/api/maps",
    response_model=List[MapItem],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["CS2 Handlers"],
)
def list_maps():
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


@app.post(
    "/api/server-start",
    response_model=ServerStartResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected Request"},
        408: {"model": ErrorResponse, "description": "Request Timeout"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["CS2 Handlers"],
)
async def start_server(request: ServerRequest):
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
            SSH_HOST, username=SSH_USER, client_keys=["ssh_key"], known_hosts=None
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
                            f"{HOST_URL}/api/servers", timeout=5
                        ) as response:
                            servers = await response.json()
                            server = next(
                                (s for s in servers if s.get("server_id") == server_id),
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


@app.post(
    "/api/server-stop",
    response_model=Union[ServerStopResponse, ErrorResponse],
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected Request"},
        408: {"model": ErrorResponse, "description": "Request Timeout"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        500: {"model": ErrorResponse, "description": "Internal server Error"},
    },
    tags=["CS2 Handlers"],
)
async def stop_server(request: ServerRequest):
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
            async with session.get(f"{HOST_URL}/api/servers", timeout=5) as response:
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
            SSH_HOST, username=SSH_USER, client_keys=["ssh_key"], known_hosts=None
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
                            f"{HOST_URL}/api/servers", timeout=5
                        ) as response:
                            servers = await response.json()

                            if server := next(
                                (s for s in servers if s.get("server_id") == server_id),
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
                    ErrorResponse(status="failed", msg="Request Timeout - server didn't stop")
                )
                return JSONResponse(status_code=408, content=error_response)

    except asyncssh.Error as e:
        error_response = jsonable_encoder(
            ErrorResponse(status="error", msg="SSH connection error")
        )
        return JSONResponse(status_code=500, content=error_response)


@app.post(
    "/api/server/settings",
    response_model=ServerSettingsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["CS2 Handlers"],
)
async def execute_commands(request: ServerSettingsRequest):
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


@app.post(
    "/api/ts3/newchannel",
    response_model=Ts3NewChannelResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Uncorrected request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["TS3 Handlers"],
)
async def ts3_new_channel(request: Ts3NewChannelRequest):
    data = request.model_dump(exclude_unset=True)

    try:
        # Подключаемся напрямую к Query порту TeamSpeak
        reader, writer = await telnetlib3.open_connection(
            TS3_SSH_HOST,  # IP вашего TS3 сервера
            TS3_SSH_PORT,  # Стандартный Query порт
        )

        # Читаем приветственное сообщение
        welcome = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        print(f"Welcome: {welcome}")

        # Аутентификация
        writer.write(f"login {TS3_SSH_USER} {TS3_SSH_PASS}\n")
        await writer.drain()
        auth_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        print(f"Auth: {auth_response}")

        # Выбираем виртуальный сервер
        writer.write("use 1\n")
        await writer.drain()
        use_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        print(f"Use: {use_response}")

        # Создаем канал
        channel_command = f'channelcreate channel_name="{data["channel_name"]}" '

        if data.get("channel_pass"):
            channel_command += f'channel_password="{data["channel_pass"]}" '

        channel_command += f"channel_maxclients=-1 " f"channel_delete_delay=600\n"

        writer.write(channel_command)
        await writer.drain()
        create_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        print(f"Create: {create_response}")

        # Закрываем соединение
        writer.write("quit\n")
        await writer.drain()
        writer.close()

        # Проверяем результат
        if "error id=0" not in create_response.lower():
            error_response = jsonable_encoder(
                ErrorResponse(status="error", msg=f"TeamSpeak error: {create_response}")
            )
            return JSONResponse(status_code=400, content=error_response)

    except Exception as e:
        error_response = jsonable_encoder(
            ErrorResponse(status="error", msg=f"Connection error: {str(e)}")
        )
        return JSONResponse(status_code=500, content=error_response)

    success_response = jsonable_encoder(
        Ts3NewChannelResponse(status="success", msg="Channel created successfully")
    )
    return JSONResponse(status_code=200, content=success_response)


@app.websocket("/api/ts3/monitoring", name="WebSocket")
async def ts_monitoring(websocket: WebSocket):
    await websocket.accept()

    reader = None
    writer = None

    try:
        while True:
            try:
                reader, writer = await asyncio.wait_for(
                    telnetlib3.open_connection(TS3_SSH_HOST, TS3_SSH_PORT, encoding='utf8', force_binary=True),
                    timeout=10.0
                )

                welcome = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                print(f"Welcome: {welcome}")

                writer.write(f"login {TS3_SSH_USER} {TS3_SSH_PASS}\n")
                await writer.drain()
                auth_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                print(f"Auth: {auth_response}")

                writer.write("use 1\n")
                await writer.drain()
                use_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                print(f"Use: {use_response}")

                while True:
                    writer.write("channellist\n")
                    await writer.drain()
                    channel_list_response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
                    parsed_channel_list = parse_channels(channel_list_response)

                    writer.write("clientlist\n")
                    await writer.drain()
                    client_list_response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
                    parsed_client_list = parse_clients(client_list_response)

                    clients_by_cid = {}
                    for client in parsed_client_list:
                        cid = client["cid"]
                        if cid and client.get("client_type") == 0:
                            if cid not in clients_by_cid:
                                clients_by_cid[cid] = []
                            clients_by_cid[cid].append(client["client_nickname"])

                    result = []
                    for channel in parsed_channel_list:
                        result.append({
                            "channel_name": channel["channel_name"],
                            "total_clients": channel["total_clients"],
                            "client_nickname": clients_by_cid.get(channel["cid"], [])
                        })

                    await websocket.send_json({
                        "data": result
                    })

                    await asyncio.sleep(10)

            except (asyncio.TimeoutError, ConnectionError) as e:
                print(f"TeamSpeak connection error: {e}")
                if writer:
                    writer.close()
                    await writer.wait_closed()

                await asyncio.sleep(5)

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()

@app.get("/api/ts3/monitoring", tags=["TS3 Handlers"], summary="WebSocket Documentation 🌐")
async def websocket_documentation():
    """
    ## WebSocket endpoint. ##
     - #### **Protocol**: WS ####
     - #### **Path**: /api/ts3/monitoring ####
     - #### **Description**: Use this endpoint for WebSocket connection. ####
    """
    return {"message": "Этот эндпоинт предназначен для WebSocket соединения. Используйте WebSocket клиент для подключения."}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=5000,
        reload=True,
        # workers=6,
    )
