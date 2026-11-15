"""Small, read-only NASA catalog adapters. No measurements are inferred."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
PDS_URL = "https://pds.nasa.gov/api/search/1/products"


class NASAUpstreamError(Exception):
    """Official source could not be retrieved or decoded."""


def _get_json(client: httpx.Client, url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = client.get(url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        return payload
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        raise NASAUpstreamError(f"NASA upstream returned HTTP {code}: {exc.response.text[:160]}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise NASAUpstreamError(f"NASA upstream unavailable or invalid response: {type(exc).__name__}") from exc


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_earth_events(client: httpx.Client, limit: int = 30) -> dict[str, Any]:
    """Recent EONET natural events; these are NOT analog discovery results."""
    payload = _get_json(client, EONET_URL, {"status": "open", "limit": limit})
    events: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        geometries = event.get("geometry") or []
        # EONET geometries are time-stamped. Use the latest usable Point.
        point = next((g for g in reversed(geometries) if isinstance(g, dict) and g.get("type") == "Point" and isinstance(g.get("coordinates"), list) and len(g["coordinates"]) >= 2), None)
        if point is None:
            continue
        lon, lat = point["coordinates"][:2]
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lon, lat)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        categories = event.get("categories") or []
        category_names = [cat.get("title", "Unknown") for cat in categories if isinstance(cat, dict)]
        sources = [s.get("url") for s in (event.get("sources") or []) if isinstance(s, dict) and isinstance(s.get("url"), str)]
        events.append({
            "id": str(event.get("id", "")), "title": str(event.get("title", "Untitled Earth event")),
            "latitude": float(lat), "longitude": float(lon), "crs": "EPSG:4326",
            "date": point.get("date"), "categories": category_names,
            "source_url": sources[0] if sources else str(event.get("link") or EONET_URL),
        })
    return {"source": "NASA EONET v3", "source_url": EONET_URL, "retrieved_at": _timestamp(),
            "kind": "earth_natural_events", "analog_results": False, "events": events}


def _first(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _first(value[0])
    return None


def fetch_planetary_products(client: httpx.Client, target: str, limit: int = 12) -> dict[str, Any]:
    """PDS product metadata, not location-specific measurements or scores."""
    # 'target_name' is a documented PDS search alias, with server-side filtering.
    payload = _get_json(client, PDS_URL, {"q": f'target_name eq "{target.capitalize()}"', "limit": limit})
    raw_items = payload.get("data", [])
    if not isinstance(raw_items, list):
        raise NASAUpstreamError("NASA PDS response does not contain a product list")
    products: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        props = item.get("properties", {})
        if not isinstance(props, dict):
            props = {}
        title = _first(props.get("pds:Identification_Area.pds:title")) or _first(props.get("title")) or _first(item.get("title"))
        identifier = _first(props.get("lidvid")) or _first(props.get("pds:Identification_Area.pds:logical_identifier")) or _first(item.get("id"))
        if not identifier:
            continue
        products.append({"id": identifier, "title": title or identifier,
                         "product_class": str(item.get("type") or props.get("product_class") or "Not supplied"),
                         "source_url": PDS_URL, "target": target})
    return {"source": "NASA Planetary Data System (PDS)", "source_url": PDS_URL,
            "retrieved_at": _timestamp(), "target": target, "kind": "planetary_archive_metadata",
            "analog_results": False, "products": products,
            "warning": "PDS search indexes archive products; entries are not measured analog matches."}
