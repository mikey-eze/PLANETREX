"""Scientific Earth analogue discovery from ALL surveyed terrain regions.

Distinct concepts:
- ranking: paired NASA-Moon/Mars vs ASTER Earth terrain only, reproducible;
- Earth context: sourced NASA climate and geological observations, independent;
- evidence filters: factual measured Earth attributes, not imaginary planetary %
Every stored Earth terrain region is eligible, including non-famous locations.
"""
from __future__ import annotations
import json
import math
import asyncio
import time
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from app.api.routes.terrain_survey import read_dataset
from app.pipeline.earth_deep_scan import fetch_power, fetch_geology
from app.api.routes.planetary_context import rock_alignment

router=APIRouter(prefix="/science",tags=["Global multi-source Earth analog discovery"])
FIELD_FILE=Path(__file__).resolve().parents[4]/"data"/"earth_science_profiles.json"
EARTH_FILTER=Literal["all","dry","cold","windy","sunny","geology","lithology","rugged"]
FIELDS={
 "dry":{"field":"precipitation_annual_mm","check":"< 250 mm during 2025", "source":"NASA POWER"},
 "cold":{"field":"air_temperature_mean_c","check":"< 0 °C 2025 annual mean", "source":"NASA POWER"},
 "windy":{"field":"wind_10m_mean_ms","check":"> 6 m/s 2025 annual mean", "source":"NASA POWER"},
 "sunny":{"field":"solar_shortwave_mean_kwh_m2_day","check":"> 5 kWh/m²/day 2025 mean", "source":"NASA POWER"},
 "geology":{"field":"geology","check":"geological map units present", "source":"Macrostrat"},
 "lithology":{"field":"lithology","check":"mapped Earth rock class corresponds to a documented site-specific NASA/USGS geology description", "source":"Macrostrat and NASA/USGS"},
 "rugged":{"field":"relief_m","check":">= 1000 m local terrain relief", "source":"NASA/METI ASTER"},
}

def read_field_profiles()->dict:
    if not FIELD_FILE.exists():
        return {"ready":False,"profiles":[],"coverage":{}}
    try:
        data=json.loads(FIELD_FILE.read_text(encoding="utf-8"))
        if data.get("schema_version")!=1 or not isinstance(data.get("profiles"),list):
            raise ValueError("Invalid Earth observation catalog")
        return {**data,"ready":True}
    except (OSError,TypeError,ValueError):
        return {"ready":False,"profiles":[],"coverage":{}}

def field_lookup()->dict:
    return {item["id"]:item for item in read_field_profiles().get("profiles",[])}

def all_earth_regions(data:dict)->list[dict]:
    pooled={}
    for p in (data.get("earth_terrain_profiles",[])+data.get("refined_earth_profiles",[])):
        if not isinstance(p,dict) or not isinstance(p.get("stats"),dict):
            continue
        pooled[p["id"]]=p
    return list(pooled.values())

def rank_global(data:dict,body:str,site_id:str)->tuple[dict,list[dict]]:
    ref=next((x for x in data["planetary_references"] if
              x["body"]==body and x["id"]==site_id),None)
    if ref is None:raise HTTPException(404,"Site has no source-backed measured terrain reference")
    a=ref["stats"]
    rows=[]
    for item in all_earth_regions(data):
        b=item["stats"]
        if b.get("coverage",0)<0.8:continue
        if any(not isinstance(b.get(key),(int,float)) or b[key]<0 for key in ("relief_m","height_std_m")):
            continue
        distance=.6*abs(math.log1p(a["relief_m"])-math.log1p(b["relief_m"])) + .4*abs(
            math.log1p(a["height_std_m"])-math.log1p(b["height_std_m"]))
        rows.append({**item,
            "terrain_distance":round(distance,4),
            "scientific_similarity_percent":None,
            "measured_terrain_features":2,
            "planned_dimensions":8,
            "measured_dimensions":1,
            "distance_kind":"Two directly compared DEM terrain metrics; other Earth observations are separate evidence.",
            "earth_evidence_supported":False})
    rows.sort(key=lambda r:(r["terrain_distance"],r["latitude"],r["longitude"]))
    return ref,rows

def earth_match_filter(row:dict,profile:dict|None,environment:str,
                       body:str="",site_id:str="")->bool:
    if environment=="all":return True
    if environment=="rugged":return row["stats"]["relief_m"]>=1000
    if profile is None:return False
    if environment=="geology":
        return bool(profile.get("earth_measurements",{}).get("geology",{}).get("units"))
    if environment=="lithology":
        rock=rock_alignment(body,site_id,
             profile.get("earth_measurements",{}).get("geology",{}).get("units",[]))
        return rock["categorical_correspondence"] is True
    power=profile.get("earth_measurements",{}).get("power_annual",{})
    field=FIELDS[environment]["field"]
    item=power.get(field,{})
    value=item.get("value") if isinstance(item,dict) else None
    if not isinstance(value,(int,float)) or not math.isfinite(value):return False
    if environment=="dry":return value<250
    if environment=="cold":return value<0
    if environment=="windy":return value>6
    if environment=="sunny":return value>5
    return False

def summarize_earth_profile(profile:dict|None)->dict:
    if not profile:return {"status":"not_profiled_in_batch","environment":{},"geology_units":[],"source_count":0}
    power=profile.get("earth_measurements",{}).get("power_annual",{})
    fields={key:value for key,value in power.items() if isinstance(value,dict) and
            value.get("value") is not None}
    geology=profile.get("earth_measurements",{}).get("geology",{})
    return {"status":"source_measured" if fields or geology.get("units") else "no_provider_data",
            "environment":fields,
            "geology_units":geology.get("units",[])[:3],
            "source_count":sum(v=="sourced" for v in profile.get("source_status",{}).values()),
            "earth_conditions":profile.get("earth_conditions",[]),
            "source_errors":profile.get("errors",[])}

@router.get("/earth-discovery")
def earth_discovery(body:Literal["moon","mars"],site_id:str,
                    environment:EARTH_FILTER="all",
                    limit:int=Query(default=40,ge=1,le=100))->dict:
    data=read_dataset()
    if not data:return {"ready":False,"reason":"Measured DEM survey unavailable","results":[],"count":0}
    ref,ranked=rank_global(data,body,site_id)
    field=read_field_profiles()
    profiles={x["id"]:x for x in field.get("profiles",[])}
    subset=[x for x in ranked if earth_match_filter(x,profiles.get(x["id"]),environment,body,site_id)]
    shortlisted=[]
    for row in subset[:limit]:
        p=profiles.get(row["id"])
        geologic_units=(p or {}).get("earth_measurements",{}).get("geology",{}).get("units",[])
        shortlisted.append({**row,"earth_evidence":summarize_earth_profile(p),
                            "planetary_geology_evidence":rock_alignment(body,site_id,geologic_units),
                            "earth_evidence_supported":p is not None and bool(p.get("earth_measurements"))})
    return {"ready":True,"planetary_reference":ref,
            "body":body,"site_id":site_id,
            "method":"Measured Earth-wide regional topography survey with optional source-backed Earth climate/geology filters",
            "environment":environment,
            "environment_definition":FIELDS.get(environment),
            "count":len(shortlisted),"total_measured_terrain_regions":len(ranked),
            "total_matching_regions":len(subset),
            "batch_earth_evidence_ready":field.get("ready",False),
            "batch_earth_evidence_coverage":field.get("coverage",{}),
            "scientific_similarity_percent":None,
            "ranking_basis":"Only DEM relief and elevation variation are directly compared with Moon or Mars; Earth climate and geology filters are independent.",
            "results":shortlisted}

@router.get("/earth-field-profile")
def earth_field_profile(earth_id:str)->dict:
    profile=field_lookup().get(earth_id)
    if not profile:raise HTTPException(404,"This Earth region has no batch-measured field profile")
    return {**profile,"source_evidence":summarize_earth_profile(profile),
            "scientific_similarity_percent":None,
            "note":"Source-derived terrestrial geology, climate and water/wind descriptors; lunar/Mars physical comparability needs separate target feature data."}

POINT_CACHE:dict[tuple[float,float],tuple[float,dict]]={}

@router.get("/earth-environmental-profile")
async def live_earth_environmental_profile(
    latitude:float=Query(ge=-90,le=90),
    longitude:float=Query(ge=-180,le=180),
)->dict:
    """Actual annual NASA meteorology and mapped geology for ANY Earth point.
    
    Separate per-provider failures never become estimated values. Cached 24h.
    """
    key=(round(latitude,4),round(longitude,4))
    old=POINT_CACHE.get(key)
    if old and time.monotonic()-old[0]<86400:
        return {**old[1],"cache_status":"cached"}
    tasks=await asyncio.gather(
        asyncio.to_thread(fetch_power,*key),
        asyncio.to_thread(fetch_geology,*key),
        return_exceptions=True)
    measurements={}
    status={}
    errors=[]
    for label,record in zip(("power_annual","geology"),tasks):
        if isinstance(record,BaseException):
            status[label]="unavailable"
            errors.append({"source":label,"error":type(record).__name__})
        else:
            status[label]="sourced"
            measurements[label]=record
    output={"latitude":key[0],"longitude":key[1],"year":"2025",
            "earth_measurements":measurements,"source_status":status,
            "errors":errors,
            "source_evidence":summarize_earth_profile({
                "earth_measurements":measurements,"source_status":status,"errors":errors}),
            "source_count":sum(v=="sourced" for v in status.values()),
            "scientific_similarity_percent":None,
            "claim":"Earth 2025 environmental and geological evidence, not paired lunar/Martian physics"}
    if len(POINT_CACHE)>=100:POINT_CACHE.pop(next(iter(POINT_CACHE)))
    if measurements:POINT_CACHE[key]=(time.monotonic(),output)
    return {**output,"cache_status":"fresh"}
