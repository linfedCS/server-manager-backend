from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import paramiko
import asyncio
import os
import re
import a2s

load_dotenv()

app = Flask(__name__)
app.debug = True
CORS(app)

SSH_HOST = os.getenv("HOST_IP", "linfed.ru")
SSH_USER = "cs"
SSH_PRIVATE_KEY = os.getenv("SSH_KEY")
if SSH_PRIVATE_KEY is not None:
    key = SSH_PRIVATE_KEY.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)
else:
    print("No ssh_key")


@app.route("/api/servers", methods=["GET"])
async def list_servers():
    servers = [
        {"id": 1, "name": "Practice 1", "ip": "linfed.ru", "port": 28011},
        {"id": 2, "name": "Practice 2", "ip": "linfed.ru", "port": 28012},
        {"id": 3, "name": "Practice 3", "ip": "linfed.ru", "port": 28013},
    ]

    async def check_server(server):
        try:
            address = (server["ip"], server["port"])
            info = await a2s.ainfo(address)
            return {
                "status": "online",
                "id": server["id"],
                "name": server["name"],
                "ip": server["ip"],
                "port": server["port"],
                "map": info.map_name,
                "players_current": info.player_count,
                "players_max": info.max_players,
            }

        except Exception as e:
            return {"status": "offline", "id": server["id"], "name": server["name"]}

    results = await asyncio.gather(*(check_server(server) for server in servers))
    return jsonify(results), 200


@app.route("/api/server-start", methods=["POST"])
def start_server():
    try:
        data = request.get_json()

        if not data or "id" not in data:
            return jsonify({"error": "No id"}), 400

        server_id = data["id"]

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, username=SSH_USER, key_filename="ssh_key")

        stdin, stdout, stderr = ssh.exec_command(f"cs2-server @prac{server_id} start")
        output = stdout.read().decode()
        error = stderr.read().decode()

        ssh.close()
        app.logger.info(output)
        app.logger.warning(error)
        return jsonify({"output": output, "error": error})
    except Exception as e:
        app.logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/server-stop", methods=["POST"])
def stop_server():
    try:
        data = request.get_json()

        if not data or "id" not in data:
            return jsonify({"error": "No id"}), 400

        server_id = data["id"]

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, username=SSH_USER, key_filename="ssh_key")

        stdin, stdout, stderr = ssh.exec_command(f"cs2-server @prac{server_id} stop")
        output = stdout.read().decode()
        error = stderr.read().decode()

        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)
        clean_output = re.sub(r"\*+\s*|\n\s*", " ", clean_output).strip()

        ssh.close()
        app.logger.info(output)
        app.logger.warning(error)
        return jsonify({"output": clean_output, "error": error})
    except Exception as e:
        app.logger.error(e)
        return jsonify({"error": str(e)}), 500
    

@app.route("/api/version", methods=["GET"])
def check_version():
    try:
        key = os.getenv("STEAM_WEB_API_KEY")
        params = {"key": key}
        response = requests.get(
            "https://api.steampowered.com/ICSGOServers_730/GetGameServersStatus/v1/",
            params=params,
        )
        if response.ok:
            data = response.json()
            return jsonify(str(data["result"]["app"]["version"])), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "Couldn't get version",
                }
            ),
            523,
        )


if __name__ == "__main__":
    app.run(host="localhost", port=5000)
