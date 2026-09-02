from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.database.session import engine

settings = get_settings()
web_dir = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
app.mount("/assets", StaticFiles(directory=web_dir), name="web-assets")


@app.get("/", include_in_schema=False)
async def website() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
