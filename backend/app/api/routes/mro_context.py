"""Mars Reconnaissance Orbiter CTX high-resolution DTM spatial discovery.

USGS NASA MRO Context Camera stereo DTMs: actual 20m-post products; we query
georeferenced footprints only. We DO NOT read pixels or use metadata as measured
terrain in PLANETREX rankings until a matching DTM is downloaded and validated.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.api.routes.sites import SITES

router=APIRouter(prefix="/science",tags=["MRO high-resolution source discovery"])
STAC="https://stac.astrogeology.usgs.gov/api"
COLLECTION="mro_ctx_controlled_usgs_dtms"
REFERENCE="https://stac.astrogeology.usgs.gov/docs/data/mars/ctxdtms/"
CITATION="https://doi.org/10.5066/P9JKVWR3"


def query_bbox(lat:float,lon:float,radius_degrees:float)->str:
    if not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError("Invalid planetary center")
    r=max(0.1,min(3.0,radius_degrees))
    # Avoid antimeridian-crossing bboxes until split queries are implemented.
    west=max(-179.99,lon-r)
    east=min(179.99,lon+r)
    return ",".join(str(round(x,5)) for x in (west,max(-89.99,lat-r),
                                                 east,min(89.99,lat+r)))


def parse_items(data:dict,limit:int)->list[dict]:
    rows=[]
    for item in (data.get("features") or [])[:limit]:
        if not isinstance(item,dict):
            continue
        assets=item.get("assets") or {}
        dtm=assets.get("dtm") if isinstance(assets,dict) else None
        url=(dtm or {}).get("href") if isinstance(dtm,dict) else None
        if not (isinstance(url,str) and url.startswith("https://")):
            continue
        props=item.get("properties") or {}
        source_url=next((x.get("href") for x in item.get("links",[])
                         if x.get("rel")=="self" and str(x.get("href","")).startswith("https://")),"")
        if not source_url:
            source_url=f"{STAC}/collections/{COLLECTION}"
        rows.append({
            "id":str(item.get("id","")), "title":str(props.get("title") or item.get("id") or "CTX DTM"),
            "source_url":source_url,"dtm_asset_url":url,
            "date":props.get("datetime") or props.get("start_datetime"),
            "bbox":item.get("bbox"),"geometry":item.get("geometry"),
            "nominal_post_spacing_m":20,
            "source_instrument":"MRO CTX stereo (NASA / USGS)",
            "measurement_status":"catalogued DTM; elevation raster not yet processed",
            "physical_similarity_percent":None
        })
    return rows


@router.get("/mro-ctx")
async def mro_ctx(site_id:Literal["perseverance","curiosity","spirit","insight"],
                  radius_degrees:float=Query(default=1.5,ge=0.1,le=3.0),
                  limit:int=Query(default=5,ge=1,le=12))->dict:
    site=next(s for s in SITES["mars"] if s["id"]==site_id)
    bbox=query_bbox(site["latitude"],site["longitude"],radius_degrees)
    params={"collections":COLLECTION,"bbox":bbox,"limit":limit}
    try:
        async with httpx.AsyncClient(timeout=17.0,follow_redirects=True) as client:
            res=await client.get(f"{STAC}/search",params=params,
                                 headers={"Accept":"application/geo+json"})
            res.raise_for_status()
            data=res.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(status_code=502,detail=f"USGS MRO CTX catalogue unavailable: {type(exc).__name__}") from exc
    if data.get("type")!="FeatureCollection":
        raise HTTPException(status_code=502,detail="USGS STAC did not return a FeatureCollection")
    records=parse_items(data,limit)
    return {"source":"NASA MRO CTX stereo DTMs, processed by USGS",
            "source_url":REFERENCE,"citation_url":CITATION,
            "collection":COLLECTION,"target":"mars","site_id":site_id,
            "site_name":site["name"],"query_bbox":bbox,
            "retrieved_at":datetime.now(timezone.utc).isoformat(),
            "count":len(records),"products":records,
            "data_kind":"high_resolution_martian_topography_product_coverage",
            "used_in_similarity_scoring":False,
            "scientific_similarity_percent":None,
            "note":"A returned item confirms available CTX DTM footprint metadata, NOT topographic comparison or validated mineral content. Individual products can have missing pixels or errors."}
