"""Second-stage coarse-to-fine Earth search around measured DEM candidate leads.

Finite offline batch. Refines geographic SEARCH spacing around top candidates; it
does not increase actual pixel/post resolution of LOLA or MOLA. Earth samples
remain ASTER GDEM over equivalent 24-km-diameter footprints.
"""
from __future__ import annotations
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.pipeline.terrain_batch import (
    EARTH_INFO, EARTH_URL, TARGET_SITES, surroundings, terrain_stats, distance
)

NEIGHBOR_OFFSETS = ((0,1),(1,0),(0,-1),(-1,0),
                    (1,1),(1,-1),(-1,1),(-1,-1))
STEP_DEG=0.45
SEEDS_PER_REFERENCE=2
MAX_EARTH_CANDIDATE_REGIONS=150
MAX_LOCATIONS_PER_CALL=75


def refine_centers(data: dict)->list[dict]:
    """Collect coarse global candidate neighbors from all six planetary sites."""
    centers={}
    for ref in data["planetary_references"]:
        key=ref["body"]+":"+ref["id"]
        for lead in data.get("screenings",{}).get(key,[])[:SEEDS_PER_REFERENCE]:
            lat0,lon0=float(lead["latitude"]),float(lead["longitude"])
            for dy,dx in NEIGHBOR_OFFSETS:
                lat=round(lat0+dy*STEP_DEG,4)
                lon=round(lon0+dx*STEP_DEG,4)
                if abs(lat)>=83 or abs(lon)>=180:
                    continue
                loc_key=f"{lat:.4f},{lon:.4f}"
                if loc_key not in centers:
                    centers[loc_key]={"latitude":lat,"longitude":lon,
                      "parent_coarse_id":lead["id"],"parent_coarse_distance":lead["terrain_distance"]}
    return list(centers.values())[:MAX_EARTH_CANDIDATE_REGIONS]


def measure_regions(client:httpx.Client,centers:list[dict],pause_s:float=1.25):
    """Sample ASTER public DEM point elevations with conservative rate limiting."""
    points=[point for c in centers for point in surroundings("earth",c["latitude"],c["longitude"])]
    elevations=[]
    for start in range(0,len(points),MAX_LOCATIONS_PER_CALL):
        chunk=points[start:start+MAX_LOCATIONS_PER_CALL]
        resp=client.get(EARTH_URL,params={"locations":"|".join(
            f"{lat:.5f},{lon:.5f}" for lat,lon in chunk)},timeout=33.0)
        resp.raise_for_status()
        payload=resp.json()
        items=payload.get("results")
        if payload.get("status")!="OK" or not isinstance(items,list) or len(items)!=len(chunk):
            raise ValueError(f"Earth DEM response malformed at offset {start}")
        for item in items:
            value=item.get("elevation")
            elevations.append(float(value) if isinstance(value,(int,float)) and
                              not isinstance(value,bool) and math.isfinite(value) else None)
        if pause_s:time.sleep(pause_s)
    out=[]
    for i,center in enumerate(centers):
        values=elevations[i*9:(i+1)*9]
        stats=terrain_stats(values)
        if stats is None:
            continue
        out.append({
            "id":f"refined_{center['latitude']:+.4f}_{center['longitude']:+.4f}",
            "name":f"Refined Earth region · {abs(center['latitude']):.2f}°{'N' if center['latitude']>=0 else 'S'}, {abs(center['longitude']):.2f}°{'E' if center['longitude']>=0 else 'W'}",
            "latitude":center["latitude"],"longitude":center["longitude"],
            "stats":stats,"source_url":EARTH_INFO,"dataset":"NASA/METI ASTER GDEM v3 via Open Topo Data",
            "kind":"refined global-search cell center with 9 terrain samples",
            "source_measurement_unit":"m","footprint_km":24,
            "search_stage":"coarse_to_fine_refinement",
            "search_spacing_deg":STEP_DEG,
            "parent_coarse_id":center["parent_coarse_id"],
            "land_cover_verified":False,
            "validation":"Cell center has DEM coverage, but biome, geology and precise land/water boundaries are not verified."
        })
    return out,{"attempted_cells":len(centers),"usable_cells":len(out),
                "elevation_points_attempted":len(points),
                "elevation_points_with_data":sum(v is not None for v in elevations),
                "neighbor_step_degrees":STEP_DEG,"seeds_per_planetary_reference":SEEDS_PER_REFERENCE,
                "method":"8-neighbor geographic local refinement around top coarse candidates of all 6 planetary sites.",
                "important":"Refines search POSITION only. NASA LOLA and MOLA DEM raster spatial resolution has NOT been increased."}


def refine(data:dict,regions:list[dict],survey:dict)->dict:
    if not data.get("screenings") or len(data.get("planetary_references",[]))<2:
        raise ValueError("Missing scientifically sourced coarse terrain profiles")
    refs={p["body"]+":"+p["id"]:p for p in data["planetary_references"]}
    new_rankings={}
    for key,ref in refs.items():
        base=data["screenings"].get(key,[])
        scored=[{**region,**distance(ref,region)} for region in regions]
        candidates=list(base)+scored
        # Geographic coordinates must be unique; smaller distance wins if duplicates.
        best={}
        for c in candidates:
            idx=(round(c["latitude"],4),round(c["longitude"],4))
            if idx not in best or c["terrain_distance"]<best[idx]["terrain_distance"]:
                best[idx]=c
        ranked=sorted(best.values(),key=lambda x:(x["terrain_distance"],x["latitude"],x["longitude"]))
        new_rankings[key]=ranked[:15]
    data["screenings"]=new_rankings
    data["refinement"]={**survey,"built_at":datetime.now(timezone.utc).isoformat(),
         "source_url":EARTH_INFO,
         "search_stage":"coarse_to_fine_refinement",
         "scientific_similarity_percent":None,
         "disclaimer":"Two terrain descriptors only. No validated planetary analog or landing suitability is inferred."}
    data["refined_earth_profiles"]=regions
    data["scientific_status"]="coarse_to_fine_two_feature_topographic_screening"
    data["built_at"]=datetime.now(timezone.utc).isoformat()
    data["limitations"].append(
      "Local Earth region search spacing improved to 0.45 degrees around selected seeds, but planetary and terrestrial DEM instrument resolution is unchanged.")
    return data


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    original=json.loads(args.input.read_text(encoding="utf-8"))
    centers=refine_centers(original)
    if len(centers)<8:
        raise ValueError("Insufficient coarse leads for automated refinement")
    with httpx.Client(timeout=35,follow_redirects=True) as client:
        regions,coverage=measure_regions(client,centers)
    if len(regions)<8:
        raise ValueError("Insufficient real Earth DEM observations in refined survey")
    revised=refine(original,regions,coverage)
    temp=args.output.with_suffix(".tmp")
    temp.parent.mkdir(parents=True,exist_ok=True)
    temp.write_text(json.dumps(revised,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps({"refined_attempted":coverage["attempted_cells"],
                      "refined_valid":coverage["usable_cells"],
                      "ranking_lengths":{k:len(v) for k,v in revised["screenings"].items()}}))


if __name__=="__main__":
    main()
