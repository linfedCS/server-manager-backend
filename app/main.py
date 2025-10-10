from fastapi.middleware.cors import CORSMiddleware
from db.lifespan import lifespan
from dotenv import load_dotenv
from fastapi import FastAPI

from core.config import get_settings
from api.routes import cs2, ts3, auth
from models.models import *



load_dotenv()
settings = get_settings()


if settings.ssh_key is not None:
    key = settings.ssh_key.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)

app = FastAPI(
    title="Linfed | Server manager API",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cs2.router, prefix="/api", tags=["CS2 Handlers"])
app.include_router(ts3.router, prefix="/api", tags=["TS3 Handlers"])
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
