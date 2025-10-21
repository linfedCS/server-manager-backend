from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from db.database import get_db_connection
from models.models import ErrorResponse


class PortManager:
    def get_free_port(self):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT port FROM ports WHERE is_occupied = FALSE ORDER BY port FOR UPDATE SKIP LOCKED"
                )
                result = cur.fetchone()

                if not result:
                    error_response = jsonable_encoder(
                        ErrorResponse(status="failed", msg="No available ports")
                    )
                    raise HTTPException(status_code=503, detail=error_response)

                port = result[0]
                return port

    def occupy_port(self, port: int, container_name: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ports SET is_occupied = TRUE, container_name = %s, occupied_at = CURRENT_TIMESTAMP WHERE port = %s AND is_occupied = FALSE",
                    (container_name, port),
                )

                return cur.rowcount > 0

    def release_port(self, container_name: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ports SET is_occupied = FALSE, container_name = NULL, occupied_at = NULL WHERE container_name = %s",
                    (container_name,),
                )

                return cur.rowcount > 0

    def release_port_by_number(self, port: int):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ports SET is_occupied = FALSE, container_name = NULL, occupied_at = NULL WHERE port = %s",
                    (port,),
                )

                return cur.rowcount > 0
