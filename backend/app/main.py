"""ASGI application entry point: uvicorn app.main:app."""

from pathlib import Path
import asyncio
import logging
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.scientific import router as scientific_router
from app.api.routes.discovery import router as discovery_router
from app.config import get_settings
from app.api.routes.profiles import router as profiles_router
from app.api.routes.sites import router as sites_router
from app.api.routes.analog_screening import router as analog_screening_router
from app.api.routes.earth_measurements import router as earth_measurements_router
from app.api.routes.terrain_survey import router as terrain_survey_router
from app.api.routes.mro_context import router as mro_context_router


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
    application.include_router(analog_screening_router)
    application.include_router(earth_measurements_router)
    application.include_router(terrain_survey_router)
    application.include_router(mro_context_router)
    explorer_dir = Path(__file__).resolve().parent / "web"
    application.mount("/explorer-assets", StaticFiles(directory=explorer_dir), name="explorer-assets")

    @application.get("/", include_in_schema=False)
    def homepage() -> RedirectResponse:
        """Make the public Render domain open the explorer directly."""
        return RedirectResponse(url="/explorer", status_code=307)

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
                "/", "/health", "/explorer", "/explorer-assets/explorer.js",
                "/exploration/sites?body=moon", "/science/profiles?body=earth",
                "/science/analog-screening?body=moon&site_id=apollo-15",
                "/science/analog-screening?body=mars&site_id=perseverance",
                "/scientific/nasa-imagery?target=moon&limit=5",
                "/scientific/nasa-imagery?target=mars&limit=5",
                "/science/earth-environment?latitude=19.4069&longitude=-155.2834",
                "/science/earthdata-catalog?keyword=elevation&limit=3",
                "/science/terrain-survey/status",
                "/science/terrain-survey/candidates?body=moon&site_id=apollo-15",
                "/science/terrain-survey/candidates?body=mars&site_id=perseverance",
                "/science/mro-ctx?site_id=perseverance&limit=2",
                "/scientific/earth-events?limit=5",
                "/scientific/planetary-products?target=moon&limit=5",
                "/scientific/planetary-products?target=mars&limit=5",
            ]
            logger = logging.getLogger("planetrex.deploy_probe")
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=23.0) as client:
                for path in paths:
                    try:
                        response = await client.get(path)
                        if ("/scientific/" in path or "/analog-screening" in path or "/earth-environment" in path or "/earthdata-catalog" in path) and response.status_code == 200:
                            payload = response.json()
                            records = payload.get("events", payload.get("products", payload.get("results", payload.get("collections", []))))
                            logger.warning("PROBE_DATA %s count=%d records=%s status=%s sources=%s",
                                           path, len(records),
                                           repr([{"id": item.get("id"), "title": item.get("title")}
                                                 for item in records[:3]])[:700], payload.get("status"), payload.get("source_count"))
                        logger.warning("PROBE %s HTTP %d bytes=%d sample=%s",
                                       path, response.status_code, len(response.content),
                                       response.text[:110].replace(chr(10), " "))
                    except Exception as exc:
                        logger.error("PROBE %s FAILED %s %s", path, type(exc).__name__, exc)
        if os.getenv("APP_ENV") == "production":
            asyncio.create_task(check())

    return application


app = create_app()
