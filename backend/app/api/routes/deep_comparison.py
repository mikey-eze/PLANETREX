"""Provenance-gated eight-domain comparison of measured planetary and Earth features.

A feature is scored ONLY if both sides supply numeric, finite, same-unit,
same-quantity, compatible-support observations with source URLs.
No missing feature is imputed. This endpoint supports arbitrary Earth sites,
including sites never previously labeled as analogs.
"""
from __future__ import annotations

import math
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter

router = APIRouter(prefix="/science", tags=["Eight-domain evidence comparison"])

DOMAINS = (
    "geology_mineralogy", "topography", "temperature_illumination",
    "water_ice", "dust_wind", "biology_habitability",
    "caves_subsurface", "engineering_resources",
)

class Observation(BaseModel):
    feature: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    source_url: str = Field(min_length=8)
    measurement_kind: str = Field(min_length=1)
    spatial_support_km: float = Field(gt=0)
    uncertainty: float | None = Field(default=None, ge=0)
    period: str | None = None

class ComparisonRequest(BaseModel):
    body: Literal["moon", "mars"]
    planetary_site_id: str = Field(min_length=1)
    earth_latitude: float = Field(ge=-90, le=90)
    earth_longitude: float = Field(ge=-180, le=180)
    planetary: dict[str, list[Observation]]
    earth: dict[str, list[Observation]]

def compare_observations(a: Observation, b: Observation) -> dict:
    reasons = []
    if a.feature != b.feature: reasons.append("different_feature")
    if a.unit != b.unit: reasons.append("different_unit")
    if a.measurement_kind != b.measurement_kind:
        reasons.append("different_measurement_kind")
    if max(a.spatial_support_km, b.spatial_support_km) / min(a.spatial_support_km, b.spatial_support_km) > 2:
        reasons.append("incompatible_spatial_support")
    if a.period and b.period and a.period != b.period:
        reasons.append("different_observation_period")
    if not (a.source_url.startswith("https://") and b.source_url.startswith("https://")):
        reasons.append("source_url_not_https")
    if not (math.isfinite(a.value) and math.isfinite(b.value)):
        reasons.append("nonfinite_value")
    if reasons:
        return {"status":"not_comparable", "reasons":reasons}
    delta = b.value - a.value
    combined_uncertainty = (
        math.hypot(a.uncertainty, b.uncertainty)
        if a.uncertainty is not None and b.uncertainty is not None else None
    )
    return {
        "status":"compared", "feature":a.feature, "unit":a.unit,
        "planetary_value":a.value, "earth_value":b.value,
        "earth_minus_planetary":delta,
        "combined_absolute_uncertainty":combined_uncertainty,
        "uncertainty_method":"root_sum_squares_if_independent" if combined_uncertainty is not None else "not_available",
        "planetary_source_url":a.source_url, "earth_source_url":b.source_url,
        "spatial_support_km":{"planetary":a.spatial_support_km,"earth":b.spatial_support_km},
        "measurement_kind":a.measurement_kind,
        "period":{"planetary":a.period,"earth":b.period},
    }

@router.post("/deep-comparison")
def deep_comparison(request: ComparisonRequest) -> dict:
    unknown = (set(request.planetary) | set(request.earth)) - set(DOMAINS)
    if unknown:
        return {"ready":False, "error":"unknown_domains", "domains":sorted(unknown)}
    domains = []
    compared_total = 0
    for domain in DOMAINS:
        planet = {x.feature:x for x in request.planetary.get(domain,[])}
        earth = {x.feature:x for x in request.earth.get(domain,[])}
        pairs = []
        for feature in sorted(set(planet) | set(earth)):
            if feature not in planet or feature not in earth:
                pairs.append({"feature":feature, "status":"missing_paired_observation",
                              "missing_side":"planetary" if feature not in planet else "earth"})
                continue
            result = compare_observations(planet[feature], earth[feature])
            pairs.append({"feature":feature, **result})
        n = sum(x["status"] == "compared" for x in pairs)
        compared_total += n
        domains.append({"domain":domain,"status":"paired" if n else "unpaired",
                        "compared_feature_count":n,"features":pairs})
    return {
        "ready":True, "body":request.body,
        "planetary_site_id":request.planetary_site_id,
        "earth_location":{"latitude":request.earth_latitude,"longitude":request.earth_longitude},
        "domains":domains, "paired_domains":sum(d["status"]=="paired" for d in domains),
        "total_domains":len(DOMAINS), "paired_features":compared_total,
        "scientific_similarity_percent":None,
        "interpretation":"Measured feature differences only. No invented values, domain score or validated suitability claim.",
        "next_step":"Supply verified and harmonized planetary and Earth measurements for unpaired domains."
    }
