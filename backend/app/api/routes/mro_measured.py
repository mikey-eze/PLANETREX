"""Actual MRO CTX elevation raster measurements, read from batch artifact.

These are high-resolution NASA/USGS CTX *scene-wide overview statistics*
(20m nominal DTM posting), not a measurement at the rover landing coordinate,
not a matched 24km MOLA footprint, and NOT an extra analog scoring dimension.
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal
import json

from fastapi import APIRouter

router=APIRouter(prefix="/science",tags=["Measured high-resolution Mars terrain"])
PATH=Path(__file__).resolve().parents[4]/"data"/"mro_dtm_overviews.json"

def read_mro():
    if not PATH.exists():return None
    try:
        data=json.loads(PATH.read_text(encoding="utf-8"))
        if data.get("schema_version")!=1 or data.get("collection")!="mro_ctx_controlled_usgs_dtms":
            return None
        return data
    except (ValueError,OSError,TypeError):
        return None

@router.get("/mro-ctx-measured")
def mro_ctx_measured(site_id:Literal["perseverance","curiosity","spirit","insight"]):
    data=read_mro()
    if data is None:
        return {"ready":False,"site_id":site_id,"count":0,"scenes":[],
                "reason":"Measured MRO CTX batch has not been published."}
    site=next((x for x in data["sites"] if x.get("site_id")==site_id),None)
    scenes=(site or {}).get("dtms",[])
    return {"ready":True,"site_id":site_id,"count":len(scenes),"scenes":scenes,
            "measured_dtm_count_global":data["measured_dtm_count"],
            "source":data["source"],"source_url":data["source_url"],
            "batch_created_at":data["generated_at"],
            "used_in_analog_scoring":False,
            "scientific_similarity_percent":None,
            "availability_note":("This source has no verified measured DTM scenes for the requested location."
                                 if not scenes else "These are sampled scene-wide CTX elevation summaries, not exact landing-site measurements."),
            "warnings":data["warnings"],"errors":(site or {}).get("errors",[])}
