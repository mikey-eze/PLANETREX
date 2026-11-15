"""Read-only official NASA metadata for the frontend's LIVE DATA mode."""
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.collectors.nasa import NASAUpstreamError, fetch_earth_events, fetch_planetary_products

router = APIRouter(tags=["scientific sources"])


@router.get("/analogs")
def analogs(target: Literal["moon", "mars"]) -> list[dict]:
    """No verified analog results exist yet. Never generate placeholder scores."""
    return []


@router.get("/scientific/earth-events")
def earth_events(limit: int = Query(default=30, ge=1, le=100)) -> dict:
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            return fetch_earth_events(client, limit)
    except NASAUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/scientific/planetary-products")
def planetary_products(target: Literal["moon", "mars"], limit: int = Query(default=12, ge=1, le=30)) -> dict:
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            return fetch_planetary_products(client, target, limit)
    except NASAUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/scientific/nasa-imagery")
def nasa_imagery(target: Literal["moon", "mars"], limit: int = Query(default=10, ge=1, le=30)) -> dict:
    """NASA Image & Video Library target-specific archive discovery, not analogs."""
    term = "apollo 15 lunar surface" if target == "moon" else "perseverance mars jezero"
    url = "https://images-api.nasa.gov/search"
    try:
        with httpx.Client(timeout=14.0, follow_redirects=True) as client:
            response = client.get(url, params={"q": term, "media_type": "image", "page_size": limit})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, f"NASA imagery source failed: {type(exc).__name__}") from exc
    items = payload.get("collection", {}).get("items", [])
    records=[]
    from datetime import datetime,timezone
    for item in items:
        if not isinstance(item,dict):continue
        metadata=(item.get("data") or [{}])[0]
        title=str(metadata.get("title") or "").strip()
        description=str(metadata.get("description") or "")[:400]
        text=(title+" "+description).lower()
        required=("moon","lunar","apollo") if target=="moon" else ("mars","jezero","perseverance")
        if not any(x in text for x in required):continue
        nasa_id=metadata.get("nasa_id")
        if not nasa_id:continue
        thumbs=[x.get("href") for x in item.get("links",[]) if x.get("render")=="image"]
        records.append({"id":nasa_id,"title":title,"description":description,
                        "image_url":thumbs[0] if thumbs else None,
                        "source_url":f"https://images.nasa.gov/details/{nasa_id}",
                        "date_created":metadata.get("date_created"),"target":target})
    return {"source":"NASA Image and Video Library","target":target,"query":term,
            "count":len(records),"products":records,"analog_results":False,
            "retrieved_at":datetime.now(timezone.utc).isoformat(),
            "source_url":url}
