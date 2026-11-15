"""Read-only, versioned global Earth terrain survey. No background HTTP scraping."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/science/terrain-survey", tags=["Batch scientific terrain screening"])
DEFAULT_PATH=Path(__file__).resolve().parents[3] / "data" / "terrain_survey.json"


def read_dataset() -> dict | None:
    if not DEFAULT_PATH.is_file():
        return None
    try:
        data=json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            return None
        if not isinstance(data.get("screenings"), dict):
            return None
        return data
    except (OSError, ValueError, TypeError):
        return None


@router.get("/status")
def terrain_status() -> dict:
    data=read_dataset()
    if data is None:
        return {"ready": False, "status": "batch_output_not_ingested",
                "description": "LOLA/MOLA and Earth ASTER batch run must complete and persist its verified output.",
                "source_metadata": {
                    "moon": "https://svs.gsfc.nasa.gov/4720/",
                    "mars": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
                    "earth": "https://www.opentopodata.org/datasets/aster/"
                },
                "scientific_similarity_percent": None}
    return {"ready": True, "status": data["scientific_status"],
            "built_at": data["built_at"],"global_scan": data["global_scan"],
            "planetary_reference_count": len(data["planetary_references"]),
            "rankings_available": list(data["screenings"]),
            "score_definition": data["score_definition"],
            "limitations": data["limitations"],"scientific_similarity_percent": None}


@router.get("/references")
def terrain_references() -> dict:
    data=read_dataset()
    if data is None:
        return {"ready":False,"references":[]}
    return {"ready":True,"references":data["planetary_references"],
            "built_at":data["built_at"]}


@router.get("/candidates")
def terrain_candidates(body:Literal["moon","mars"],site_id:str,
                       limit:int=Query(default=10,ge=1,le=15)) -> dict:
    data=read_dataset()
    if data is None:
        return {"ready":False,"body":body,"site_id":site_id,"results":[],
                "count":0,"reason":"Batch dataset not generated or not deployed.",
                "scientific_similarity_percent":None}
    key=f"{body}:{site_id}"
    rows=data["screenings"].get(key)
    if rows is None:
        return {"ready":True,"body":body,"site_id":site_id,"results":[],
                "count":0,"reason":"No scientifically measured reference footprint for this site.",
                "scientific_similarity_percent":None}
    reference=next((r for r in data["planetary_references"]
                    if r["body"]==body and r["id"]==site_id),None)
    return {"ready":True,"body":body,"site_id":site_id,
            "reference":reference,"results":rows[:limit],"count":len(rows),
            "global_scan":data["global_scan"],
            "score_definition":data["score_definition"],
            "limitations":data["limitations"],
            "scientific_similarity_percent":None,
            "note":"Lower numerical terrain distance means more similar topographic vertical variation. No physical similarity percentage is scientifically justified."}
