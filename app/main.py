from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta
from handlers.server_handler import process_data
import time
import requests
import paramiko
import asyncio
import os
import aiofiles
import json
import a2s

load_dotenv()

app = Flask(__name__)
app.debug = True
CORS(app)

API_URL = "/static/openapi.yaml"
SWAGGER_URL = "/api/docs"

swagger = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        "app_name": "Linfed | Server manager API"
    },
)
app.register_blueprint(swagger)

SSH_HOST = os.getenv("HOST_IP", "linfed.ru")
SSH_USER = os.getenv("SSH_USER")
SSH_PRIVATE_KEY = os.getenv("SSH_KEY")
if SSH_PRIVATE_KEY is not None:
    key = SSH_PRIVATE_KEY.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)
else:
    print("No ssh_key")


@app.route("/api/servers", methods=["GET"])
async def list_servers():
    async with aiofiles.open("servers.json", "r") as f:
        servers = json.loads(await f.read())

    async with aiofiles.open("maps.json", "r") as f:
        maps = json.loads(await f.read())

    map_name_to_id = {map_item["name"]: map_item["id"] for map_item in maps}

    async def check_server(server):
        try:
            address = (server["ip"], server["port"])
            info = await a2s.ainfo(address)
            map_id = map_name_to_id.get(info.map_name, info.map_name)
            return {
                "status": "online",
                "id": server["id"],
                "name": server["name"],
                "ip": server["ip"],
                "port": server["port"],
                "map_id": map_id,
                "players_current": int(info.player_count),
                "players_max": info.max_players,
            }

        except Exception as e:
            return {"status": "offline", "id": server["id"], "name": server["name"]}

    results = await asyncio.gather(*(check_server(server) for server in servers))
    return jsonify(results), 200


@app.route("/api/maps", methods=["GET"])
async def list_maps():
    async with aiofiles.open("maps.json", "r") as f:
        data = await f.read()
        maps = json.loads(data)
        return jsonify(maps), 200


@app.route("/api/server-start", methods=["POST"])
def start_server():
    try:
        data = request.get_json()

        if not data or "id" not in data:
            return jsonify({"error": "No id"}), 400

        server_id = data["id"]
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(SSH_HOST, username=SSH_USER, key_filename="ssh_key")

            stdin, stdout, stderr = ssh.exec_command(
                f"cs2-server @prac{server_id} start"
            )
            output = stdout.read().decode()
            error = stderr.read().decode()

            if error.strip():
                return jsonify({"error": f"SSH command error: {error}"}), 500

            timeout_seconds = 60
            check_interval = 1
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=timeout_seconds)

            while datetime.now() < end_time:
                try:
                    response = requests.get(
                        "https://dev.linfed.ru/api/servers", timeout=check_interval
                    )
                    servers = response.json()

                    server = next(
                        (s for s in servers if s.get("id") == server_id), None
                    )
                    if server and server.get("status") == "online":
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "data": server,
                                }
                            ),
                            200,
                        )

                except requests.exceptions.RequestException:
                    pass

                time.sleep(check_interval)

            return (
                jsonify(
                    {
                        "status": "failed",
                        "message": "Error when starting the server",
                    }
                ),
                200,
            )

        finally:
            if ssh:
                ssh.close()

    except Exception as e:
        app.logger.error(f"Server start error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/server-stop", methods=["POST"])
def stop_server():
    try:
        data = request.get_json()

        if not data or "id" not in data:
            return jsonify({"error": "No id"}), 400

        server_id = data["id"]
        try:
            response = requests.get("https://dev.linfed.ru/api/servers", timeout=10)
            servers = response.json()
            server = next((s for s in servers if s.get("id") == server_id), None)

            if not server:
                return jsonify({"error": "Server not found"}), 404

            # Проверяем, есть ли игроки на сервере
            if server.get("players_current", 0) >= 1:
                return jsonify({
                    "status": "failed",
                    "message": "You can't stop the server while there are players on it",
                    "data": server
                }), 200

        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Could not check server status"}), 500

        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(SSH_HOST, username=SSH_USER, key_filename="ssh_key")

            stdin, stdout, stderr = ssh.exec_command(
                f"cs2-server @prac{server_id} stop"
            )
            output = stdout.read().decode()
            error = stderr.read().decode()

            if error.strip():
                return jsonify({"error": f"SSH command error: {error}"}), 500

            timeout_seconds = 60
            check_interval = 1
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=timeout_seconds)

            while datetime.now() < end_time:
                try:
                    response = requests.get(
                        "https://dev.linfed.ru/api/servers", timeout=check_interval
                    )
                    servers = response.json()

                    server = next(
                        (s for s in servers if s.get("id") == server_id), None
                    )

                    if server and server.get("status") == "offline":
                        return (
                            jsonify(
                                {
                                    "status": "success",
                                    "data": server,
                                }
                            ),
                            200,
                        )

                except requests.exceptions.RequestException:
                    pass

                time.sleep(check_interval)

            return (
                jsonify(
                    {
                        "status": "failed",
                        "message": "Error when stopping the server",
                    }
                ),
                200,
            )

        finally:
            if ssh:
                ssh.close()

    except Exception as e:
        app.logger.error(f"Server stop error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/server/settings", methods=["POST"])
def execute_commands():
    try:
        data = request.get_json()

        if not data or "id" not in data:
            return jsonify({"error": "No id"}), 400

        results = process_data(data)

        if not results:
            return jsonify({"error": "No valid data"}), 400

        return jsonify(results)

    except Exception as e:
        app.logger.error(f"Error execute commands: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="localhost", port=5000)
