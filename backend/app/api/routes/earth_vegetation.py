"""NASA Terra MOD13Q1 Earth vegetation-index evidence, quality screened.

An NDVI observation describes terrestrial vegetation cover/activity only. It
does NOT measure extraterrestrial life or make a habitability match.
"""
from __future__ import annotations
import math
import time
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, HTTPException, Query
from app.api.routes.earth_surface import subset_group, BASE, DOCS

router = APIRouter(prefix="/science", tags=["Earth vegetation evidence"])
PRODUCT = "MOD13Q1"
CACHE: dict[tuple[float,float], tuple[float,dict]] = {}
BAND_NDVI = "250m 16 days NDVI"
BAND_QA = "250m 16 days pixel reliability"

def parse_ndvi(payload:dict)->dict:
    dates = subset_group(payload)
    good = []
    rejected = 0
    snow_ice = 0
    for date, values in dates.items():
        dn = values.get(BAND_NDVI)
        qa = values.get(BAND_QA)
        if qa == 2:
            snow_ice += 1
        if not isinstance(qa,int) or isinstance(qa,bool) or qa != 0:
            rejected += 1
            continue
        if not isinstance(dn,(int,float)) or isinstance(dn,bool) or not math.isfinite(dn) or not -2000 <= dn <= 10000:
            rejected += 1
            continue
        good.append(float(dn) * .0001)
    return {
        "ndvi_mean":round(sum(good)/len(good),4) if good else None,
        "ndvi_min":round(min(good),4) if good else None,
        "ndvi_max":round(max(good),4) if good else None,
        "unit":"unitless vegetation reflectance index (-0.2 to 1.0)",
        "quality_accepted_samples":len(good),
        "rejected_or_missing_samples":rejected,
        "observed_snow_ice_quality_flags":snow_ice,
        "total_dates":len(dates),
        "measurement_kind":"NASA MODIS 16-day Earth vegetation index; center pixel approximately 250 m",
        "qa_rule":"Only pixel reliability 0 (good), valid raw NDVI -2000 to 10000, scale factor 0.0001.",
        "interpretation":"Lower values can correspond to less vegetation, bare ground, water or snow; do not automatically classify an environment from NDVI alone.",
    }

async def fetch_ndvi(latitude:float,longitude:float)->dict:
    async with httpx.AsyncClient(follow_redirects=True,timeout=27.0) as client:
        r=await client.get(f"{BASE}/{PRODUCT}/subset",params={
            "latitude":round(latitude,5),"longitude":round(longitude,5),
            "startDate":"A2025001","endDate":"A2025033",
            "kmAboveBelow":1,"kmLeftRight":1,
        },headers={"Accept":"application/json"})
        r.raise_for_status()
        response=r.json()
    measured=parse_ndvi(response)
    return {
        "latitude":latitude,"longitude":longitude,"retrieved_at":datetime.now(timezone.utc).isoformat(),
        "source":"NASA MODIS Terra via ORNL DAAC",
        "source_url":DOCS,"product":PRODUCT,"period":"January–February 2025",
        "measurement":measured,"observations_available":measured["ndvi_mean"] is not None,
        "biology_claim":False,"extraterrestrial_habitability_claim":False,
        "note":"Vegetation evidence is useful to characterize a terrestrial analog test site; it is not a measurement of Martian or lunar life.",
        "scientific_similarity_percent":None,
    }

@router.get("/earth-vegetation")
async def earth_vegetation(latitude:float=Query(ge=-83,le=83),
                           longitude:float=Query(ge=-180,le=180))->dict:
    key=round(latitude,4),round(longitude,4)
    cached=CACHE.get(key)
    if cached and time.monotonic()-cached[0]<86400:
        return {**cached[1],"cache_status":"cached"}
    try:
        payload=await fetch_ndvi(*key)
    except (httpx.HTTPError,ValueError,TypeError) as exc:
        raise HTTPException(status_code=502,detail=f"NASA vegetation observations unavailable: {type(exc).__name__}") from exc
    if len(CACHE)>=80:CACHE.pop(next(iter(CACHE)))
    CACHE[key]=(time.monotonic(),payload)
    return {**payload,"cache_status":"fresh"}
