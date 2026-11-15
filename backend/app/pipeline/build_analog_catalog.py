"""Build a reproducible analog catalog from persisted, source-backed measurements.

No API requests are made during catalog generation. All measured Earth regions
remain eligible, whether or not previously identified as analogs.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from app.api.routes.earth_discovery import all_earth_regions
from app.api.routes.planetary_context import rock_alignment
from app.pipeline.paired_domain_scoring import score_domains

DOMAINS = ("geology_mineralogy", "topography", "temperature_illumination",
           "water_ice", "dust_wind", "biology_habitability",
           "caves_subsurface", "engineering_resources")

def valid_number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def build(terrain:dict, earth_profiles:dict, paired_observations:dict|None=None) -> dict:
    if terrain.get("schema_version") != 1 or not terrain.get("planetary_references"):
        raise ValueError("Missing verified planetary terrain reference catalog")
    if earth_profiles.get("schema_version") != 1:
        raise ValueError("Missing Earth evidence catalog")
    earth = all_earth_regions(terrain)
    profiles = {p["id"]:p for p in earth_profiles.get("profiles",[]) if "id" in p}
    observations=paired_observations or {}
    planet_observations=observations.get('planetary',{})
    earth_observations=observations.get('earth',{})
    results = {}
    for ref in terrain["planetary_references"]:
        pstats = ref["stats"]
        key = f'{ref["body"]}:{ref["id"]}'
        ranked = []
        for candidate in earth:
            stats = candidate["stats"]
            if stats.get("coverage",0) < .8:
                continue
            if not all(valid_number(stats.get(f)) and stats[f]>=0 for f in ("relief_m","height_std_m")):
                continue
            if not all(valid_number(pstats.get(f)) and pstats[f]>=0 for f in ("relief_m","height_std_m")):
                continue
            measures=[]
            differences=[]
            for feature in ("relief_m","height_std_m"):
                pv,ev=pstats[feature],stats[feature]
                measures.append({"feature":feature,"unit":"m","planetary_value":pv,"earth_value":ev,
                                 "earth_minus_planetary":round(ev-pv,3),
                                 "planetary_source_url":ref["source_url"],
                                 "earth_source_url":candidate["source_url"]})
                differences.append(abs(math.log1p(pv)-math.log1p(ev)))
            terrain_distance=round(.6*differences[0]+.4*differences[1],5)
            # An explicitly heuristic similarity index, NOT calibrated probability.
            # Its coverage is always displayed alongside the score.
            terrain_similarity_percent=round(100*math.exp(-terrain_distance),1)
            field=profiles.get(candidate["id"],{})
            measurements=field.get("earth_measurements",{})
            geo=measurements.get("geology",{})
            rock=rock_alignment(ref["body"],ref["id"],geo.get("units",[]))
            # Categorical lithology is an independent evidence signal; not
            # falsely counted as quantified mineral abundances.
            domains={domain:{"status":"unpaired","paired_feature_count":0} for domain in DOMAINS}
            domains["topography"]={"status":"paired","paired_feature_count":2,
                                    "distance":terrain_distance,"measurements":measures,
                                    "method":"0.6*log1p relief delta + 0.4*log1p elevation SD delta"}
            domains["geology_mineralogy"]={
                "status":"categorical_context_only" if rock["categorical_correspondence"] is not None else "unpaired",
                "paired_feature_count":0,
                "earth_geology_source_url":geo.get("source_url"),
                "planetary_geology_reference":rock.get("planetary_reference"),
                "rock_category_correspondence":rock["categorical_correspondence"]}
            power=measurements.get("power_annual",{})
            context={k:{"value":v["value"],"unit":v["unit"],"source_url":v.get("source_url"),
                        "period":v.get("period"),"sample_days":v.get("sample_days")}
                     for k,v in power.items() if isinstance(v,dict) and valid_number(v.get("value"))}
            paired_score=score_domains(planet_observations.get(key,{}),earth_observations.get(candidate['id'],{}))
            ranked.append({
                "earth_id":candidate["id"],"name":candidate.get("name",candidate["id"]),
                "latitude":candidate["latitude"],"longitude":candidate["longitude"],
                "terrain_distance":terrain_distance,
                "measured_terrain_similarity_percent":terrain_similarity_percent,
                "score_definition":"100 * exp(-terrain_distance); descriptive heuristic, not scientific validation",
                "domain_coverage_percent":12.5,
                "paired_domains":1,"total_domains":8,"paired_features":2,
                "earth_environmental_context":context,
                "paired_domain_scores":paired_score,
                "domains":domains,
                "source_status":field.get("source_status",{}),
                "scientific_similarity_percent":None,
                "previous_analog_certification_required":False})
        ranked.sort(key=lambda x:(x["terrain_distance"],x["latitude"],x["longitude"]))
        for i,row in enumerate(ranked,1):row["terrain_rank"]=i
        results[key]={"planetary_reference":ref,"candidate_count":len(ranked),"candidates":ranked}
    return {
        "schema_version":1,"built_at":datetime.now(timezone.utc).isoformat(),
        "method":"All measured Earth DEM regions compared against NASA lunar/Martian DEM references; independent Earth geology and climate context",
        "domain_names":list(DOMAINS),
        "interpretation":"Measured terrain ranking with independently sourced terrestrial context. Missing planetary pairs are not scored.",
        "science_coverage":{"quantitatively_paired_domains":["topography"],
                            "other_domains":"awaiting harmonized source-backed planetary and Earth measurements"},
        "results":results}

def main():
    root=Path(__file__).resolve().parents[3]
    parser=argparse.ArgumentParser()
    parser.add_argument("--terrain",type=Path,default=root/"data"/"terrain_survey.json")
    parser.add_argument("--earth",type=Path,default=root/"data"/"earth_science_profiles.json")
    parser.add_argument("--output",type=Path,default=root/"data"/"analog_catalog.json")
    parser.add_argument("--paired-observations",type=Path,default=root/"data"/"paired_observations.json")
    args=parser.parse_args()
    paired=json.loads(args.paired_observations.read_text()) if args.paired_observations.is_file() else {}
    catalog=build(json.loads(args.terrain.read_text()),json.loads(args.earth.read_text()),paired)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temp=args.output.with_suffix(".tmp")
    temp.write_text(json.dumps(catalog,indent=2,allow_nan=False),encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps({"references":len(catalog["results"]),
                      "candidates":{k:v["candidate_count"] for k,v in catalog["results"].items()},
                      "output":str(args.output)}))

if __name__=="__main__":main()
