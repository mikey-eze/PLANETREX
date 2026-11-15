"""NASA POWER Earth-only atmospheric, precipitation and insolation descriptors.

No Earth observations are treated as interchangeable with Mars wind/dust,
lunar regolith, lunar temperatures or planetary ice observations.
"""
from __future__ import annotations
import math
import time
from datetime import datetime,timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

router=APIRouter(prefix="/science",tags=["Earth surface and hydrology evidence"])
URL="https://power.larc.nasa.gov/api/temporal/daily/point"
DOCUMENTATION="https://power.larc.nasa.gov/docs/methodology/data/sources_hydrology/"
CACHE={}
PARAMS={
 "T2M":{"label":"Earth 2-metre air temperature (NOT ground temperature)","unit":"°C","aggregation":"mean",
        "dimension":"atmospheric_environment","source_kind":"NASA POWER MERRA-2-informed Earth climate"},
 "PRECTOTCORR":{"label":"Earth corrected January precipitation","unit":"mm/31 days","aggregation":"sum",
        "dimension":"hydrologic_environment","source_kind":"NASA POWER corrected precipitation, not lunar/Martian ice"},
 "WS10M":{"label":"Earth 10-metre wind speed","unit":"m/s","aggregation":"mean",
        "dimension":"aeolian","source_kind":"Terrestrial atmospheric wind; lunar vacuum is not comparable"},
 "ALLSKY_SFC_SW_DWN":{"label":"Earth incoming shortwave radiation","unit":"kWh/m²/day","aggregation":"mean",
        "dimension":"illumination","source_kind":"Terrestrial atmosphere/surface solar irradiance; not lunar direct irradiance"}
}

def summarize_power(data:dict)->dict:
    parameter=data.get("properties",{}).get("parameter",{})
    if not isinstance(parameter,dict):raise ValueError("No NASA POWER parameter time series")
    out={}
    for code,definition in PARAMS.items():
        time_series=parameter.get(code)
        if not isinstance(time_series,dict):
            out[code]={**definition,"value":None,"sample_days":0,"status":"missing_from_provider"}
            continue
        nums=[float(n) for n in time_series.values() if isinstance(n,(int,float))
              and not isinstance(n,bool) and math.isfinite(n) and n>-900]
        if not nums:
            out[code]={**definition,"value":None,"sample_days":0,"status":"missing_from_provider"}
            continue
        val=sum(nums) if definition["aggregation"]=="sum" else sum(nums)/len(nums)
        out[code]={**definition,"value":round(val,3),"sample_days":len(nums),
                   "status":"source_derived","period":"2025-01-01/2025-01-31",
                   "source":"NASA POWER AG (Earth)","source_url":URL}
    return out

@router.get("/earth-processes")
async def earth_processes(
    latitude:float=Query(ge=-90,le=90),longitude:float=Query(ge=-180,le=180)):
    key=(round(latitude,3),round(longitude,3))
    if key in CACHE and time.monotonic()-CACHE[key][0]<24*3600:
        return {**CACHE[key][1],"cache_status":"cached"}
    params={"parameters":",".join(PARAMS),"community":"AG",
            "latitude":key[0],"longitude":key[1],
            "start":"20250101","end":"20250131","format":"JSON"}
    try:
        async with httpx.AsyncClient(timeout=22.0,follow_redirects=True) as client:
            response=await client.get(URL,params=params)
            response.raise_for_status()
            payload=response.json()
        data=summarize_power(payload)
    except httpx.HTTPStatusError as exc:
        import logging
        logging.getLogger("planetrex.power").warning("NASA POWER AG rejected parameters %s: HTTP %d response=%s", ",".join(PARAMS), exc.response.status_code, exc.response.text[:850])
        raise HTTPException(status_code=502,
            detail=f"NASA POWER surface process request returned upstream HTTP {exc.response.status_code}") from exc
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(502,detail=f"NASA POWER surface process data unavailable: {type(exc).__name__}") from exc
    result={
        "latitude":key[0],"longitude":key[1],
        "source":"NASA POWER (AG terrestrial environmental data)",
        "source_url":DOCUMENTATION,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),
        "period":"January 2025","parameters":data,
        "count_measured_parameters":sum(x["value"] is not None for x in data.values()),
        "interpretation":"Earth-only gridded model and satellite-informed hydrology/meteorology, NOT matched extraterrestrial environmental measurements.",
        "planetary_environment_comparisons_ready":False,
        "scientific_similarity_percent":None
    }
    if len(CACHE)>70:CACHE.pop(next(iter(CACHE)))
    CACHE[key]=(time.monotonic(),result)
    return {**result,"cache_status":"fresh"}
