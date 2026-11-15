"""ASGI application entry point: uvicorn app.main:app."""

from pathlib import Path
import asyncio
import logging
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.scientific import router as scientific_router
from app.api.routes.discovery import router as discovery_router
from app.config import get_settings
from app.api.routes.profiles import router as profiles_router
from app.api.routes.sites import router as sites_router
from app.api.routes.analog_screening import router as analog_screening_router
from app.api.routes.earth_measurements import router as earth_measurements_router
from app.api.routes.earth_geology import router as earth_geology_router
from app.api.routes.earth_vegetation import router as earth_vegetation_router
from app.api.routes.earth_discovery import router as earth_discovery_router
from app.api.routes.terrain_survey import router as terrain_survey_router
from app.api.routes.mro_context import router as mro_context_router
from app.api.routes.analog_evidence import router as analog_evidence_router
from app.api.routes.earth_surface import router as earth_surface_router
from app.api.routes.mro_measured import router as mro_measured_router
from app.api.routes.earth_processes import router as earth_processes_router
from app.api.routes.science_coverage import router as science_coverage_router
from app.api.routes.deep_comparison import router as deep_comparison_router
from app.api.routes.analog_catalog import router as analog_catalog_router


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
    application.include_router(earth_geology_router)
    application.include_router(earth_vegetation_router)
    application.include_router(earth_discovery_router)
    application.include_router(terrain_survey_router)
    application.include_router(mro_context_router)
    application.include_router(analog_evidence_router)
    application.include_router(earth_surface_router)
    application.include_router(mro_measured_router)
    application.include_router(earth_processes_router)
    application.include_router(science_coverage_router)
    application.include_router(deep_comparison_router)
    application.include_router(analog_catalog_router)
    explorer_dir = Path(__file__).resolve().parent / "web"
    application.mount("/explorer-assets", StaticFiles(directory=explorer_dir), name="explorer-assets")

    @application.get("/", include_in_schema=False)
    def homepage() -> RedirectResponse:
        """Make the public Render domain open the explorer directly."""
        return RedirectResponse(url="/observatory", status_code=307)

    # Same-origin texture bytes permit smooth per-pixel sphere projection in Canvas.
    # Only these three explicitly licensed Solar System Scope CC BY 4.0 assets
    # can be requested; this is not an arbitrary internet proxy.
    texture_urls = {
        "moon": "https://www.solarsystemscope.com/textures/download/2k_moon.jpg",
        "mars": "https://www.solarsystemscope.com/textures/download/2k_mars.jpg",
        "earth": "https://www.solarsystemscope.com/textures/download/2k_earth_daymap.jpg",
    }
    texture_cache: dict[str, bytes] = {}
    texture_locks = {body: asyncio.Lock() for body in texture_urls}

    @application.get("/visual/texture/{body}.jpg", include_in_schema=False)
    async def visual_texture(body: str) -> Response:
        url = texture_urls.get(body)
        if url is None:
            raise HTTPException(status_code=404, detail="Unknown planet texture")
        async with texture_locks[body]:
            if body not in texture_cache:
                try:
                    async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
                        result = await client.get(url)
                        result.raise_for_status()
                    content = result.content
                    if not content.startswith(b"\xff\xd8\xff") or not 100000 < len(content) < 12000000:
                        raise ValueError("Upstream texture is not a valid-size JPEG")
                    texture_cache[body] = content
                except (httpx.HTTPError, ValueError) as exc:
                    raise HTTPException(status_code=502, detail="Source texture unavailable") from exc
        return Response(content=texture_cache[body], media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    @application.get("/observatory", include_in_schema=False)
    def observatory() -> FileResponse:
        """Mission observatory: dual planetary stages and source-backed telemetry."""
        return FileResponse(explorer_dir / "observatory.html")

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
                "/", "/health", "/observatory", "/explorer", "/explorer-assets/observatory.js", "/explorer-assets/observatory.css", "/explorer-assets/explorer.js",
                "/exploration/sites?body=moon", "/science/profiles?body=earth",
                "/science/analog-screening?body=moon&site_id=apollo-15",
                "/science/analog-screening?body=mars&site_id=perseverance",
                "/scientific/nasa-imagery?target=moon&limit=5",
                "/scientific/nasa-imagery?target=mars&limit=5",
                "/science/earth-environment?latitude=19.4069&longitude=-155.2834",
                "/science/earth-geology?latitude=19.4069&longitude=-155.2834",
                "/science/earth-discovery?body=moon&site_id=apollo-15&limit=5",
                "/science/earth-discovery?body=mars&site_id=perseverance&environment=dry&limit=5",
                "/science/earthdata-catalog?keyword=elevation&limit=3",
                "/science/coverage",
                "/science/mro-ctx-measured?site_id=perseverance",
                "/science/terrain-survey/status",
                "/science/terrain-survey/candidates?body=moon&site_id=apollo-15",
                "/science/terrain-survey/candidates?body=mars&site_id=perseverance",
                "/science/mro-ctx?site_id=perseverance&limit=2",
                "/science/mro-ctx-measured?site_id=perseverance",
                "/science/analog-evidence?body=mars&site_id=perseverance&earth_id=earth_-15_-070",
                "/scientific/earth-events?limit=5",
                "/scientific/planetary-products?target=moon&limit=5",
                "/scientific/planetary-products?target=mars&limit=5",
                "/science/earth-processes?latitude=19.4069&longitude=-155.2834",
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
