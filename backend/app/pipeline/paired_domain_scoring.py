"""Evidence-gated, reproducible eight-domain descriptive similarity indices.

Percentages are model indices (0-100), not probabilities or validation.
Missing domain evidence never contributes a zero or an invented match.
Every feature must be a source-backed paired observation with matching units,
physical quantity, measurement kind, and reasonably matched spatial support.
"""
from __future__ import annotations
import math
from collections import defaultdict

# Reference scales are declared model choices, not empirical uncertainty.
# A feature outside this registry is NOT silently scored.
FEATURES = {
 "geology_mineralogy":{"basalt_fraction":{"unit":"fraction","kind":"mineral_fraction","scale":0.25},
                       "silica_mass_fraction":{"unit":"fraction","kind":"bulk_chemistry_fraction","scale":0.2}},
 "topography":{"relief_m":{"unit":"m","kind":"regional_dem_relief","scale":1000.0},
               "height_std_m":{"unit":"m","kind":"regional_dem_height_std","scale":350.0}},
 "temperature_illumination":{"surface_temperature_k":{"unit":"K","kind":"surface_temperature","scale":50.0},
                              "incident_solar_w_m2":{"unit":"W/m2","kind":"surface_incident_solar","scale":350.0}},
 "water_ice":{"surface_water_mass_fraction":{"unit":"fraction","kind":"surface_water_fraction","scale":0.1}},
 "dust_wind":{"surface_particle_d50_um":{"unit":"um","kind":"particle_median_diameter","scale":150.0}},
 "biology_habitability":{"surface_organic_carbon_fraction":{"unit":"fraction","kind":"organic_carbon_fraction","scale":0.05}},
 "caves_subsurface":{"void_depth_m":{"unit":"m","kind":"measured_subsurface_void_depth","scale":100.0}},
 "engineering_resources":{"bearing_strength_kpa":{"unit":"kPa","kind":"measured_bearing_strength","scale":250.0},
                          "rock_abundance_fraction":{"unit":"fraction","kind":"surface_rock_abundance","scale":0.2}},
}

def _finite(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

def score_pair(a,b,spec):
    if not isinstance(a,dict) or not isinstance(b,dict):
        return {"status":"missing_observation"}
    if not all(_finite(x.get("value")) for x in (a,b)):
        return {"status":"invalid_numeric_value"}
    if not all(x.get("unit")==spec["unit"] and x.get("measurement_kind")==spec["kind"] for x in (a,b)):
        return {"status":"incompatible_units_or_physical_quantities"}
    if not all(isinstance(x.get("source_url"),str) and x["source_url"].startswith("https://") for x in (a,b)):
        return {"status":"missing_source_provenance"}
    sa,sb=a.get("spatial_support_km"),b.get("spatial_support_km")
    if not _finite(sa) or not _finite(sb) or min(sa,sb)<=0 or max(sa,sb)/min(sa,sb)>2:
        return {"status":"incompatible_spatial_support"}
    # A phase-specific or local-time-specific temperature cannot be compared
    # with a different time-of-day/season sampling without explicit matching.
    if a.get("sampling_context") != b.get("sampling_context"):
        return {"status":"incompatible_sampling_context"}
    delta=abs(a["value"]-b["value"])
    score=100*math.exp(-delta/spec["scale"])
    return {"status":"compared","similarity_percent":round(score,2),
            "absolute_difference":round(delta,6),"unit":spec["unit"],
            "planetary_value":a["value"],"earth_value":b["value"],
            "planetary_source_url":a["source_url"],"earth_source_url":b["source_url"],
            "scale":spec["scale"],"scale_type":"declared_descriptive_model_parameter"}

def score_domains(planetary,earth):
    results={}
    for domain,features in FEATURES.items():
        pairs={}
        for feature,spec in features.items():
            pairs[feature]=score_pair(planetary.get(domain,{}).get(feature),
                                      earth.get(domain,{}).get(feature),spec)
        values=[v["similarity_percent"] for v in pairs.values() if v["status"]=="compared"]
        results[domain]={"status":"scored" if values else "insufficient_paired_data",
                         "similarity_percent":round(sum(values)/len(values),2) if values else None,
                         "feature_coverage_percent":round(100*len(values)/len(features),2),
                         "features":pairs}
    scored=[v["similarity_percent"] for v in results.values() if v["similarity_percent"] is not None]
    complete=all(v["feature_coverage_percent"]==100 for v in results.values())
    return {"domains":results,"domain_coverage_percent":round(100*len(scored)/len(FEATURES),2),
            "observed_domain_mean_percent":round(sum(scored)/len(scored),2) if scored else None,
            "overall_eight_domain_similarity_percent":round(sum(scored)/len(scored),2) if complete else None,
            "fully_covered":complete,
            "method":"Equal-feature average within domain; equal-domain average when all domains fully observed. Feature index=100*exp(-absolute_difference/declared_scale).",
            "interpretation":"Descriptive model similarity indices, not scientifically calibrated probabilities or proof of planetary suitability."}
