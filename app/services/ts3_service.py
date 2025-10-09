from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from handlers.ts3_parser import parse_channels, parse_clients
from core.config import get_settings
from models.models import *

import telnetlib3
import asyncio
import asyncio

settings = get_settings()


class TS3Service:
    async def ts3_new_channel(self, request: Ts3NewChannelRequest):
        data = request.model_dump(exclude_unset=True)

        try:
            # Подключаемся напрямую к Query порту TeamSpeak
            reader, writer = await telnetlib3.open_connection(
                settings.ts3_host,  # IP вашего TS3 сервера
                settings.ts3_port,
                encoding="utf8",
                force_binary=True,
            )

            # Читаем приветственное сообщение
            welcome = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            print(f"Welcome: {welcome}")

            # Аутентификация
            writer.write(f"login {settings.ts3_user} {settings.ts3_pass}\n")
            await writer.drain()
            auth_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            print(f"Auth: {auth_response}")

            # Выбираем виртуальный сервер
            writer.write("use 1\n")
            await writer.drain()
            use_response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            print(f"Use: {use_response}")

            # Создаем канал
            channel_command = f'channelcreate channel_name={data["channel_name"]} '

            if data.get("channel_pass"):
                channel_command += f'channel_password={data["channel_pass"]} '

            channel_command += f"channel_maxclients=-1 " f"channel_delete_delay=180\n"

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
                    ErrorResponse(
                        status="error", msg=f"TeamSpeak error: {create_response}"
                    )
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

    async def ts_monitoring(self, websocket: WebSocket):
        await websocket.accept()

        reader = None
        writer = None

        try:
            while True:
                try:
                    reader, writer = await asyncio.wait_for(
                        telnetlib3.open_connection(
                            settings.ts3_host,
                            settings.ts3_port,
                            encoding="utf8",
                            force_binary=True,
                        ),
                        timeout=10.0,
                    )

                    welcome = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                    print(f"Welcome: {welcome}")

                    writer.write(f"login {settings.ts3_user} {settings.ts3_pass}\n")
                    await writer.drain()
                    auth_response = await asyncio.wait_for(
                        reader.read(1024), timeout=5.0
                    )
                    print(f"Auth: {auth_response}")

                    writer.write("use 1\n")
                    await writer.drain()
                    use_response = await asyncio.wait_for(
                        reader.read(1024), timeout=5.0
                    )
                    print(f"Use: {use_response}")

                    while True:
                        writer.write("channellist\n")
                        await writer.drain()
                        channel_list_response = await asyncio.wait_for(
                            reader.read(4096), timeout=5.0
                        )
                        parsed_channel_list = parse_channels(channel_list_response)

                        writer.write("clientlist\n")
                        await writer.drain()
                        client_list_response = await asyncio.wait_for(
                            reader.read(4096), timeout=5.0
                        )
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
                            result.append(
                                {
                                    "channel_name": channel["channel_name"],
                                    "total_clients": channel["total_clients"],
                                    "client_nickname": clients_by_cid.get(
                                        channel["cid"], []
                                    ),
                                }
                            )

                        await websocket.send_json({"data": result})

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
