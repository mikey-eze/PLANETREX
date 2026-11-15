"""Point geology context for Earth candidates from public geologic mapping.

These are mapped *terrestrial* bedrock geologic units and their source
references. They do not constitute quantified mineral abundances, physical
sample laboratory measurements, or comparable Moon/Mars geology.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Query

router=APIRouter(prefix="/science",tags=["Terrestrial geology evidence"])
MACROSTRAT="https://macrostrat.org/api/v2/geologic_units/map"
DOCS="https://dev.macrostrat.org/docs/data-services"
_CACHE={}
TTL=24*3600
MAX_ROWS=100
FIELDS=("name","strat_name","lith","liths","descrip","comments","age","t_int_name",
        "t_int_age","b_int_name","b_int_age","source_id","source","ref_id","map_id","unit_id")


def parse_geology(payload:dict)->list[dict]:
    if not isinstance(payload,dict) or payload.get("success") is False:
        raise ValueError("Invalid geological map response")
    root=payload.get("success",{})
    raw=root.get("data") if isinstance(root,dict) else payload.get("data")
    if isinstance(raw,dict):raw=[raw]
    if raw is None:raw=[]
    if not isinstance(raw,list):
        raise ValueError("Unexpected geologic map data structure")
    results=[]
    for item in raw[:10]:
        if not isinstance(item,dict):continue
        selected={k:item[k] for k in FIELDS if k in item and isinstance(item[k],(str,int,float,list)) and item[k] is not None}
        if selected:
            results.append(selected)
    return results


@router.get("/earth-geology")
async def earth_geology(latitude:float=Query(ge=-90,le=90),
                        longitude:float=Query(ge=-180,le=180))->dict:
    key=(round(latitude,4),round(longitude,4))
    cached=_CACHE.get(key)
    if cached and time.monotonic()-cached[0]<TTL:
        return {**cached[1],"cache_status":"cached"}
    try:
        async with httpx.AsyncClient(timeout=17,follow_redirects=True) as client:
            response=await client.get(MACROSTRAT,params={"lat":key[0],"lng":key[1],"response":"long"})
            response.raise_for_status()
            units=parse_geology(response.json())
        status="mapped" if units else "no_mapped_units"
        error=None
    except (httpx.HTTPError,ValueError,TypeError) as exc:
        units=[];status="upstream_unavailable";error=type(exc).__name__
    output={
      "latitude":key[0],"longitude":key[1],
      "source":"Macrostrat v2 integrated geologic maps",
      "source_url":DOCS,
      "request_url":f"https://macrostrat.org/api/v2/geologic_units/map?lat={key[0]}&lng={key[1]}",
      "attribution":"Macrostrat, original national/regional geological survey compilers; CC BY 4.0",
      "retrieved_at":datetime.now(timezone.utc).isoformat(),
      "status":status,"error":error,"units":units,"count":len(units),
      "is_planetary_comparison":False,"validated_lithology_match":False,
      "note":"This is mapped Earth geology at a point. Map scale, rock-unit uncertainty and planetary mineral evidence must be independently assessed before comparing Moon or Mars.",
    }
    if status!="upstream_unavailable":
        if len(_CACHE)>=MAX_ROWS:_CACHE.pop(next(iter(_CACHE)))
        _CACHE[key]=(time.monotonic(),output)
    return {**output,"cache_status":"fresh"}
