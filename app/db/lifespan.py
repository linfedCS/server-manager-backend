from contextlib import asynccontextmanager
from .database import init_pool, close_pool

@asynccontextmanager
async def lifespan(app):
    try:
        init_pool()
        yield
    finally:
        close_pool()
