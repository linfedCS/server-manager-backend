from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from db.lifespan import lifespan
from dotenv import load_dotenv

from core.config import get_settings
from api.routes import cs2, ts3, auth
from models.models import *

import secrets


load_dotenv()
settings = get_settings()
security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = settings.docs_admin_username.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )

    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = settings.docs_admin_password.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


if settings.ssh_key is not None:
    key = settings.ssh_key.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)

app = FastAPI(
    title="Linfed | Server manager API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    # openapi_url="/api/openapi.json",
    servers=[
        {"url": f"{settings.host_url}"},
    ],
    openapi_tags=[
        {"name": "CS2 Handlers", "description": ""},
        {"name": "TS3 Handlers", "description": ""},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/docs", response_class=HTMLResponse, )
async def get_docs(username: str = Depends(authenticate)):
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs")

app.include_router(cs2.router, prefix="/api/cs2", tags=["CS2 Handlers"])
app.include_router(ts3.router, prefix="/api/ts3", tags=["TS3 Handlers"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication Handlers"])



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=5000,
        reload=True,
        # workers=6,
    )
