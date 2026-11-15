"""ASGI application entry point: uvicorn app.main:app."""

from pathlib import Path
import asyncio
import logging
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.scientific import router as scientific_router
from app.api.routes.discovery import router as discovery_router
from app.config import get_settings
from app.api.routes.profiles import router as profiles_router
from app.api.routes.sites import router as sites_router


def create_app() -> FastAPI:
    """Construct the FastAPI application without network or dataset side effects."""
    settings = get_settings()
    application = FastAPI(
        title="PLANETREX API",
        description="Planetary analog discovery — official NASA catalog metadata (not similarity results).",
        version="0.1.0",
        debug=settings.debug,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(scientific_router)
    application.include_router(discovery_router)
    application.include_router(profiles_router)
    application.include_router(sites_router)
    explorer_dir = Path(__file__).resolve().parent / "web"
    application.mount("/explorer-assets", StaticFiles(directory=explorer_dir), name="explorer-assets")

    @application.get("/explorer", include_in_schema=False)
    def explorer() -> FileResponse:
        """Dependency-free browser fallback, served by FastAPI."""
        return FileResponse(explorer_dir / "index.html")

    @application.on_event("startup")
    async def production_probe_startup() -> None:
        """Probe real endpoints once per deploy; log failures rather than fake success."""
        async def check() -> None:
            await asyncio.sleep(3)
            port = os.environ.get("PORT", "10000")
            paths = [
                "/health", "/explorer", "/explorer-assets/explorer.js",
                "/exploration/sites?body=moon", "/science/profiles?body=earth",
                "/scientific/earth-events?limit=5",
                "/scientific/planetary-products?target=moon&limit=5",
                "/scientific/planetary-products?target=mars&limit=5",
            ]
            logger = logging.getLogger("planetrex.deploy_probe")
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=23.0) as client:
                for path in paths:
                    try:
                        response = await client.get(path)
                        logger.warning("PROBE %s HTTP %d bytes=%d sample=%s",
                                       path, response.status_code, len(response.content),
                                       response.text[:110].replace(chr(10), " "))
                    except Exception as exc:
                        logger.error("PROBE %s FAILED %s %s", path, type(exc).__name__, exc)
        if os.getenv("APP_ENV") == "production":
            asyncio.create_task(check())

    return application


app = create_app()
