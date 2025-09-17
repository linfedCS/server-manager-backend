import paramiko
import json
import os

SSH_HOST = os.getenv("HOST_IP", "linfed.ru")
SSH_USER = os.getenv("SSH_USER")
SSH_PRIVATE_KEY = os.getenv("SSH_KEY")
if SSH_PRIVATE_KEY is not None:
    key = SSH_PRIVATE_KEY.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)
else:
    print("No ssh key")


def handler_map(data):
    try:
        ssh = None
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, username=SSH_USER, key_filename="ssh_key")

        server_id = data["id"]
        map_id = data["map_id"]

        with open("maps.json", "r") as file:
            maps_data = json.load(file)

        map_dict = {item["id"]: item["name"] for item in maps_data}
        map_name = map_dict.get(map_id)

        command = f"map {map_name}"

        stdin, stdout, stderr = ssh.exec_command(
            f"cs2-server @prac{server_id} exec {command}"
        )
        error = stderr.read().decode()

        if error.strip():
            return {"error": f"SSH command error: {error}"}
        return {"status": "success"}

    finally:
        if ssh:
            ssh.close()


def process_data(data):
    results = {}

    for field, handler in field_handler.items():
        if field in data:
            results[field] = handler(data)

    return results

field_handler = {"map_id": handler_map}
