"""Explain two-feature DEM screening in a scientific evidence matrix.

The API never recasts terrain distances as a percent or treats a NASA image/DTM
archive hit as a processed mineral or surface-temperature measurement.
"""
from __future__ import annotations
from typing import Literal
import math
from fastapi import APIRouter, HTTPException, Query

from app.api.routes.terrain_survey import read_dataset

router=APIRouter(prefix="/science",tags=["Explainable planetary analog evidence"])

LIMITATIONS={
 "moon":{
  "atmosphere":"Lunar near-vacuum is not reproduced on Earth.",
  "gravity":"Lunar gravity (~1/6 of Earth) is not reproduced.",
  "radiation":"Unshielded deep-space radiation is not reproduced by terrain similarity.",
  "operations":"Potential field tests: off-road mobility, slope-aware route planning and autonomous navigation. Local feasibility requires ground verification."
 },
 "mars":{
  "atmosphere":"Martian atmosphere is extremely thin compared with Earth's.",
  "gravity":"Martian gravity (~0.38 of Earth) is not reproduced.",
  "radiation":"Surface radiation conditions differ substantially from Earth.",
  "operations":"Potential field tests: rover traction, navigation, slope-sensitive drilling plans and remote geological survey. Local feasibility requires ground verification."
 }
}

# Every dimension must have both source-backed planetary AND terrestrial
# measurements to count as comparable. These are not substitute scores.
NOT_EVALUATED=[
 ("geology_mineralogy","Unmeasured mineral abundances / lithology; MRO CRISM archive may provide future source data."),
 ("temperature_illumination","NASA POWER Earth 2m air temperature is not comparable with Diviner lunar or planetary surface temperatures without harmonization."),
 ("water_ice","No paired ice/regolith-water measurements."),
 ("dust_wind","Earth wind and Martian dust conditions not harmonized; lunar atmosphere is absent."),
 ("biology_habitability","No paired habitability indicators; no evidence of extraterrestrial biology assumed."),
 ("caves_subsurface","No paired validated subsurface/cave measurements."),
 ("engineering_resources","No paired local bearing strength, rock size, radiation protection, or resource measurements.")
]

def terrain_sensitivity(reference:dict, shortlist:list[dict], earth_id:str)->dict:
    """Calculate ranking sensitivity to the arbitrary relief-vs-SD weights.

    The shortlist is *only* the already-returned candidate list, so this is
    not a global rank and not a statistical confidence interval.
    """
    a=reference["stats"]
    weights=(0.3,0.4,0.5,0.6,0.7)
    outputs=[]
    for w in weights:
        ranks=[]
        for earth in shortlist:
            b=earth["stats"]
            dr=abs(math.log1p(a["relief_m"])-math.log1p(b["relief_m"]))
            ds=abs(math.log1p(a["height_std_m"])-math.log1p(b["height_std_m"]))
            ranks.append((w*dr+(1-w)*ds,earth["id"]))
        ranks.sort()
        for i,(distance,identifier) in enumerate(ranks,1):
            if identifier==earth_id:
                outputs.append({"relief_weight":w,"height_std_weight":round(1-w,2),
                                "shortlist_rank":i,"distance":round(distance,4)})
                break
    if not outputs:
        raise ValueError("Earth candidate must be part of shortlisted comparisons")
    positions=[x["shortlist_rank"] for x in outputs]
    return {
        "kind":"deterministic_score_weight_sensitivity",
        "weights_tested":[x["relief_weight"] for x in outputs],
        "results":outputs,
        "best_rank_in_shortlist":min(positions),
        "worst_rank_in_shortlist":max(positions),
        "stable_shortlist_position":len(set(positions))==1,
        "uncertainty_type":"method_weight_sensitivity_only",
        "calibrated_statistical_confidence":None,
        "interpretation":"Rank changes when arbitrary weights change; ranking sensitivity is not measurement uncertainty, source-validation, or a scientific match percentage."
    }


@router.get("/analog-evidence")
def analog_evidence(body:Literal["moon","mars"],site_id:str,earth_id:str)->dict:
    data=read_dataset()
    if data is None:
        return {"ready":False,"reason":"Evidence-based DEM batch not published","comparison":None}
    key=f"{body}:{site_id}"
    ref=next((r for r in data["planetary_references"] if
              r["body"]==body and r["id"]==site_id),None)
    if ref is None:
        raise HTTPException(404,detail="No measurement-backed planetary reference")
    candidate=next((r for r in data["screenings"].get(key,[])
                    if r["id"]==earth_id),None)
    if candidate is None:
        raise HTTPException(404,detail="Earth region is not in this site's screened shortlist")
    p=ref["stats"];e=candidate["stats"]
    pair={
      "dimension":"topography",
      "status":"compared_measurements",
      "feature_count":2,
      "surface_scale_km":24,
      "measured_comparisons":[
        {"feature":"Elevation relief over sampled window","unit":"m",
         "planetary_value":p["relief_m"],"earth_value":e["relief_m"],
         "absolute_difference_m":round(abs(e["relief_m"]-p["relief_m"]),1)},
        {"feature":"Elevation standard deviation over sampled window","unit":"m",
         "planetary_value":p["height_std_m"],"earth_value":e["height_std_m"],
         "absolute_difference_m":round(abs(e["height_std_m"]-p["height_std_m"]),1)}
      ],
      "planetary_data":{"dataset":ref["dataset"],"source_url":ref["source_url"],
                        "angular_pixel_spacing_deg":ref["horizontal_sampling_deg"],
                        "sample_count":p["sample_count"],"coverage":p["coverage"]},
      "earth_data":{"dataset":candidate["dataset"],"source_url":candidate["source_url"],
                    "sample_count":e["sample_count"],"coverage":e["coverage"],
                    "search_stage":candidate.get("search_stage","coarse_grid"),
                    "land_cover_verified":candidate.get("land_cover_verified",False)},
      "score":{"name":"topographic_variation_distance",
               "value":candidate["terrain_distance"],"lower_is_better":True,
               "formula":data["score_definition"],
               "scientific_similarity_percent":None,
               "calibration_status":"not scientifically calibrated",
               "dimension_coverage_fraction":0.125}
    }
    differences={
       "relief_difference_m":round(e["relief_m"]-p["relief_m"],1),
       "height_std_difference_m":round(e["height_std_m"]-p["height_std_m"],1),
       "physical_environment_mismatches":{
          "atmosphere":LIMITATIONS[body]["atmosphere"],
          "gravity":LIMITATIONS[body]["gravity"],
          "radiation":LIMITATIONS[body]["radiation"]
       },
       "unmeasured_dimensions":[{"dimension":name,"status":"insufficient_comparable_measurements","reason":reason}
                                 for name,reason in NOT_EVALUATED]
    }
    return {
      "ready":True,"planetary_location":{"body":body,"site_id":site_id,
               "name":ref["name"],"latitude":ref["lat"],"longitude":ref["lon"]},
      "earth_location":{"id":candidate["id"],"name":candidate["name"],
                        "latitude":candidate["latitude"],"longitude":candidate["longitude"]},
      "measured_dimensions":[pair],"not_measured":differences["unmeasured_dimensions"],
      "where_analogy_breaks_down":differences,
      "possible_research_use":LIMITATIONS[body]["operations"],
      "discovery_method":"Systematic Earth global grid + nearby refinement around top terrain matches. Not a validated novel site discovery.",
      "number_of_matched_dimensions":1,
      "total_planned_dimensions":8,
      "source_batch_date":data["built_at"],
      "global_grid":data["global_scan"],
      "refinement":data.get("refinement"),
      "terrain_rank_sensitivity":terrain_sensitivity(ref,data["screenings"].get(key,[]),earth_id),
      "scientific_similarity_percent":None,
      "scientific_status":"preliminary_measurement_based_terrain_screening",
      "important":"The method compares only 2 regional DEM descriptors, not lunar/Martian climate, mineralogy or base suitability. Local ground truth and uncertainties are essential."
    }
