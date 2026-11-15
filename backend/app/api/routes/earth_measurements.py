"""Measured terrestrial environment and source catalogs.

POWER T2M is model/observation-informed near-surface air temperature, not
planetary soil temperature. Copernicus DEM elevation is a sampled Earth point.
Both remain independent of the descriptive tag-overlap ranking.
"""
from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/science", tags=["Earth measurements and science source discovery"])
POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
ELEVATION = "https://api.open-meteo.com/v1/elevation"
CMR = "https://cmr.earthdata.nasa.gov/search/collections.json"
OPEN_TOPO = "https://api.opentopodata.org/v1/aster30m"

_cache: dict[tuple[float, float], tuple[float, dict]] = {}
CACHE_SECONDS = 12 * 3600
MAX_CACHE = 80

def _observed(values):
    return [float(v) for v in values if isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v > -900]

def _time():
    return datetime.now(timezone.utc).isoformat()

async def _power(client, lat, lon):
    response = await client.get(POWER, params={
        "parameters": "T2M,T2M_MAX,T2M_MIN",
        "community": "AG", "longitude": lon, "latitude": lat,
        "start": "20250101", "end": "20250131", "format": "JSON"
    })
    response.raise_for_status()
    data = response.json()
    parameter = data.get("properties", {}).get("parameter", {})
    if not isinstance(parameter, dict):
        raise ValueError("POWER returned no parameter data")
    records = {}
    for code, label in [
        ("T2M", "January 2025 average 2m air temperature"),
        ("T2M_MAX", "January 2025 mean daily maximum 2m air temperature"),
        ("T2M_MIN", "January 2025 mean daily minimum 2m air temperature"),
    ]:
        series = parameter.get(code, {})
        nums = _observed(series.values()) if isinstance(series, dict) else []
        records[code] = {
            "label": label, "value": round(sum(nums) / len(nums), 2) if nums else None,
            "unit": "°C", "sample_days": len(nums),
            "period": "2025-01-01/2025-01-31", "source": "NASA POWER",
            "source_url": POWER,
            "kind": "historical gridded terrestrial 2m air temperature",
            "note": "Area-scale atmospheric dataset sampled at a point, not ground-surface temperature or temperature on Moon/Mars."
        }
    return records

async def _elev(client, lat, lon):
    response = await client.get(ELEVATION, params={"latitude": lat, "longitude": lon})
    response.raise_for_status()
    nums = response.json().get("elevation")
    if not isinstance(nums, list) or len(nums) != 1:
        raise ValueError("Unexpected elevation response")
    value = nums[0]
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid elevation measurement")
    return {
        "label": "Ground elevation above mean sea level", "value": float(value),
        "unit": "m", "source": "Copernicus DEM GLO-90 via Open-Meteo",
        "source_url": ELEVATION, "source_data": "Copernicus DEM GLO-90 (2021)",
        "kind": "90m DEM value at coordinate",
        "note": "Earth point elevation alone cannot be compared to lunar or Martian elevation across different datums."
    }

async def _fallback_aster_elev(client, lat, lon):
    """NASA ASTER GDEM via independent Open Topo Data mirror; distinguish provenance."""
    response = await client.get(OPEN_TOPO, params={"locations": f"{lat},{lon}"})
    response.raise_for_status()
    payload = response.json()
    records = payload.get("results") or []
    if payload.get("status") != "OK" or len(records) != 1:
        raise ValueError("ASTER elevation service returned no valid single-point response")
    value = records[0].get("elevation")
    if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("ASTER DEM missing value at this coordinate")
    return {
        "label": "Ground elevation from ASTER DEM", "value": float(value),
        "unit": "m", "source": "NASA ASTER GDEM via Open Topo Data",
        "source_url": OPEN_TOPO, "source_data": "ASTER global DEM ~30m",
        "kind": "DEM model sampled at point (independent backup)",
        "note": "Fallback NASA-derived Earth elevation; distinct model/datum from Copernicus. Not directly comparable to lunar/Mars elevation."
    }

@router.get("/earth-environment")
async def earth_environment(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
) -> dict:
    """Return independently fetched Earth measurements with partial-failure state."""
    key=(round(latitude, 4), round(longitude, 4))
    old=_cache.get(key)
    if old is not None and time.monotonic() - old[0] < CACHE_SECONDS:
        return {**old[1], "cache_status": "cached"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        power, elev = await asyncio.gather(
            _power(client, *key), _elev(client, *key), return_exceptions=True
        )
    measurements = {}
    errors = []
    fallback_used = False
    if isinstance(elev, Exception):
        try:
            async with httpx.AsyncClient(timeout=16, follow_redirects=True) as fallback_client:
                elev = await _fallback_aster_elev(fallback_client, *key)
                fallback_used = True
        except Exception as fallback_exc:
            errors.append({"source": "NASA ASTER GDEM backup", "reason": type(fallback_exc).__name__})
    if isinstance(power, Exception):
        errors.append({"source": "NASA POWER", "reason": type(power).__name__})
    else:
        measurements.update(power)
    if isinstance(elev, Exception):
        errors.append({"source": "Copernicus DEM via Open-Meteo", "reason": type(elev).__name__})
    else:
        measurements["DEM_ELEVATION"] = elev
    result = {
        "latitude": key[0], "longitude": key[1], "retrieved_at": _time(),
        "measurements": measurements, "source_errors": errors,
        "source_count": (not isinstance(power, Exception)) + (not isinstance(elev, Exception)),
        "elevation_fallback_used": fallback_used,
        "status": "available" if not errors else ("partial" if measurements else "upstream_unavailable"),
        "scientific_similarity_percent": None,
        "notes": [
            "These are real terrestrial measurements; the Moon/Mars reference has not been quantitatively harmonized.",
            "Do not infer a physical-similarity percentage from these numbers or from geological tags.",
            "NASA POWER historical January 2025 climate window is fixed for reproducibility; it is not live weather."
        ],
    }
    if len(_cache) >= MAX_CACHE:
        _cache.pop(next(iter(_cache)))
    if measurements:
        _cache[key]=(time.monotonic(), result)
    return {**result, "cache_status": "fresh"}

@router.get("/earthdata-catalog")
async def earthdata_catalog(
    keyword: str = Query(min_length=3, max_length=70),
    limit: int = Query(default=6, ge=1, le=12),
) -> dict:
    """Search NASA Earthdata CMR collection metadata; do not call it measured analog evidence."""
    try:
        async with httpx.AsyncClient(timeout=17, follow_redirects=True) as client:
            response = await client.get(CMR, params={"keyword": keyword, "page_size": limit})
            response.raise_for_status()
            data=response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"NASA Earthdata CMR unavailable: {type(exc).__name__}") from exc
    entries=data.get("feed", {}).get("entry", [])
    rows=[]
    for item in entries[:limit]:
        rows.append({"id": item.get("id"), "title": item.get("title"),
                     "short_name": item.get("short_name"),"version":item.get("version_id"),
                     "source_url": CMR,
                     "data_center": item.get("data_center"),
                     "concept_id": item.get("id"),
                     "catalog_url": "https://cmr.earthdata.nasa.gov/search/concepts/" + str(item.get("id")) if item.get("id") else CMR})
    return {
        "source": "NASA Earthdata Common Metadata Repository", "keyword": keyword,
        "retrieved_at": _time(), "collections": rows, "count": len(rows),
        "kind": "dataset_discovery_metadata", "analog_results": False,
        "warning": "Catalog entries are not downloaded scientific measurements."
    }
