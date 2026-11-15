"""Serve persisted discovery results, never recompute global analysis per request."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Query

router=APIRouter(prefix="/science",tags=["Batch analog discovery catalog"])
CATALOG=Path(__file__).resolve().parents[4]/"data"/"analog_catalog.json"

def read_catalog():
    if not CATALOG.is_file():
        return None
    try:
        value=json.loads(CATALOG.read_text(encoding="utf-8"))
        if value.get("schema_version")!=1 or not isinstance(value.get("results"),dict):
            return None
        return value
    except (ValueError,OSError,TypeError):
        return None

@router.get("/analog-catalog/status")
def status():
    data=read_catalog()
    if data is None:
        return {"ready":False,"reason":"Run python -m app.pipeline.build_analog_catalog from backend and deploy data/analog_catalog.json"}
    return {"ready":True,"built_at":data["built_at"],"method":data["method"],
            "science_coverage":data["science_coverage"],
            "references":{k:v["candidate_count"] for k,v in data["results"].items()}}

@router.get("/analog-catalog/candidates")
def candidates(body:Literal["moon","mars"],site_id:str,
               limit:int=Query(default=20,ge=1,le=200),
               offset:int=Query(default=0,ge=0),
               require_earth_geology:bool=False):
    data=read_catalog()
    if data is None:
        raise HTTPException(503,"Batch catalog not generated or deployed")
    record=data["results"].get(f"{body}:{site_id}")
    if record is None:
        raise HTTPException(404,"No measured planetary reference for this site")
    rows=record["candidates"]
    if require_earth_geology:
        rows=[r for r in rows if r["domains"]["geology_mineralogy"]["status"]=="categorical_context_only"]
    return {"ready":True,"planetary_reference":record["planetary_reference"],
            "total":len(rows),"offset":offset,"limit":limit,
            "results":rows[offset:offset+limit],
            "ranking_basis":"Measured DEM relief and height variation only",
            "scientific_similarity_percent":None}

@router.get("/analog-catalog/site")
def site_comparison(body:Literal["moon","mars"],site_id:str,earth_id:str):
    data=read_catalog()
    if data is None:
        raise HTTPException(503,"Batch catalog not generated or deployed")
    record=data["results"].get(f"{body}:{site_id}")
    if record is None:
        raise HTTPException(404,"Planetary reference not in measured catalog")
    row=next((r for r in record["candidates"] if r["earth_id"]==earth_id),None)
    if row is None:
        raise HTTPException(404,"Earth region not in measured catalog")
    return {"ready":True,"body":body,"site_id":site_id,
            "planetary_reference":record["planetary_reference"],
            "earth_candidate":row,
            "terrain_similarity_percent":row["measured_terrain_similarity_percent"],
            "coverage_percent":row["domain_coverage_percent"],
            "overall_eight_domain_similarity_percent":None,
            "domain_results":row["domains"],
            "score_disclaimer":"Terrain percentage is a descriptive transform of two DEM metrics, not a calibrated scientific match. Other domains are not yet paired."}
