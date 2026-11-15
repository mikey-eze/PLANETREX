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
