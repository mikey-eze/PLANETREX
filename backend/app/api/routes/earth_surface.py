"""Read real MODIS/Terra Earth surface temperature, with strict QC.

NASA ORNL DAAC TESViS REST subsets (not AIR temperature, not Moon/Mars).
MOD11A2: 8-day composite, raw 0.02 K per DN. QC_Day/Night mandatory
0-1 bits: accept only class 00 (good). Filter fill values and preserve sample
counts. These observations are Earth-only context pending planetary harmonization.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

router=APIRouter(prefix="/science",tags=["NASA MODIS Earth surface conditions"])
BASE="https://modis.ornl.gov/rst/api/v1"
DOCS="https://modis.ornl.gov/data/modis_webservice.html"
SOURCE_PRODUCT="MOD11A2"
START="A2025001"
END="A2025033"
CACHE:dict[tuple[float,float],tuple[float,dict]]={}
MAX_CACHE=60


def subset_group(payload:dict)->dict[str,dict]:
    """Extract single-cell per-band daily sequence from ORNL subset response."""
    rows=payload.get("subset",[])
    ncols=payload.get("ncols")
    nrows=payload.get("nrows")
    if not isinstance(rows,list) or not isinstance(ncols,int) or not isinstance(nrows,int):
        raise ValueError("Invalid NASA MODIS response structure")
    if not 1 <= ncols*nrows <= 100:
        raise ValueError("Unexpected MODIS region dimensions")
    result={}
    for row in rows:
        if not isinstance(row,dict):continue
        band=row.get("band")
        date=row.get("modis_date")
        data=row.get("data")
        if not isinstance(band,str) or not isinstance(date,str) or not isinstance(data,list) or len(data)!=ncols*nrows:
            continue
        # Midpoint of explicitly requested single-pixel region, or center pixel
        val=data[(nrows//2)*ncols+(ncols//2)]
        result.setdefault(date,{})[band]=val
    return result


def temperature_summary(payload:dict,band_name:str,qc_name:str)->dict:
    by_date=subset_group(payload)
    temps=[];rejects=0
    for row in by_date.values():
        dn=row.get(band_name)
        qc=row.get(qc_name)
        if not isinstance(dn,(int,float)) or isinstance(dn,bool) or not math.isfinite(dn) or dn<7500 or dn>20000:
            rejects+=1
            continue
        if not isinstance(qc,int) or isinstance(qc,bool) or (qc&0b11)!=0:
            rejects+=1
            continue
        temp_c=float(dn)*0.02-273.15
        if not -125 <= temp_c <= 75:
            rejects+=1;continue
        temps.append(round(temp_c,3))
    return {
        "value":round(sum(temps)/len(temps),2) if temps else None,
        "min_c":round(min(temps),2) if temps else None,
        "max_c":round(max(temps),2) if temps else None,
        "unit":"°C","accepted_composites":len(temps),
        "rejected_or_missing_composites":rejects,
        "total_composites":len(by_date),
        "qc_rule":"MOD11A2 mandatory QC bits 0-1 must equal 0 (good); DN × 0.02 K minus 273.15.",
        "period":"2025-01-01 through 2025-02-02",
        "product":SOURCE_PRODUCT,"source":"NASA MODIS Terra via ORNL DAAC",
        "source_url":DOCS,
        "measurement_kind":"8-day composite Earth LAND SURFACE temperature at approximately 1 km native resolution",
        "warning":"Cloud/quality-screened composites, not maximum/minimum temperature extremes or an exact 24-km area average.",
    }


async def fetch_surface(latitude:float,longitude:float)->dict:
    async with httpx.AsyncClient(follow_redirects=True,timeout=25.0) as client:
        res=await client.get(f"{BASE}/{SOURCE_PRODUCT}/subset",params={
          "latitude":round(latitude,5),"longitude":round(longitude,5),
          "startDate":START,"endDate":END,"kmAboveBelow":0,"kmLeftRight":0
        },headers={"Accept":"application/json"})
        res.raise_for_status()
        payload=res.json()
    if not isinstance(payload,dict):
        raise ValueError("MODIS response not a JSON object")
    day=temperature_summary(payload,"LST_Day_1km","QC_Day")
    night=temperature_summary(payload,"LST_Night_1km","QC_Night")
    return {"latitude":latitude,"longitude":longitude,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),
        "source":"NASA ORNL DAAC MODIS TESViS","product":SOURCE_PRODUCT,
        "source_url":DOCS,"period":"January 2025",
        "measurements":{"surface_day":day,"surface_night":night},
        "observations_available":day["accepted_composites"]>0 or night["accepted_composites"]>0,
        "coverage_note":"Earth-only temperature observations; not a Moon or Mars temperature comparison.",
        "scientific_similarity_percent":None
    }


@router.get("/earth-surface")
async def earth_surface(
    latitude:float=Query(ge=-83,le=83),
    longitude:float=Query(ge=-180,le=180)):
    key=(round(latitude,4),round(longitude,4))
    found=CACHE.get(key)
    if found and time.monotonic()-found[0]<86400:
        return {**found[1],"cache_status":"cached"}
    try:
        record=await fetch_surface(*key)
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(502,f"NASA MODIS subset retrieval failed: {type(exc).__name__}") from exc
    if len(CACHE)>=MAX_CACHE:CACHE.pop(next(iter(CACHE)))
    CACHE[key]=(time.monotonic(),record)
    return {**record,"cache_status":"fresh"}
