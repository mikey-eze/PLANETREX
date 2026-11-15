"""Sourced, site-specific planetary geological reference descriptions.

These are literature observations, not harmonized orbital mineral abundance
rasters; mapped Earth lithology can be screened categorically but not converted
into a quantitative mineral similarity percent.
"""
from __future__ import annotations

REFERENCES={
  "moon:apollo-15":{
    "geologic_feature":"Basaltic lunar mare / exposed volcanic lavas near Hadley Rille",
    "expected_earth_lithology":"basalt",
    "region_scope":"Hadley Rille mare lava exposures, NOT all nearby highlands",
    "source":"USGS / NASA Apollo 15 field geology",
    "source_url":"https://www.usgs.gov/publications/geologic-setting-apollo-15-samples"
  },
  "mars:perseverance":{
    "geologic_feature":"Sedimentary delta deposits within Jezero Crater",
    "expected_earth_lithology":"sedimentary",
    "region_scope":"Jezero ancient river delta, not all igneous crater-floor lithologies",
    "source":"NASA Perseverance Jezero Delta research",
    "source_url":"https://science.nasa.gov/resource/detailed-panorama-of-mars-jezero-crater-delta/"
  },
  "mars:curiosity":{
    "geologic_feature":"Layered sedimentary rocks at Gale Crater / Mount Sharp",
    "expected_earth_lithology":"sedimentary",
    "region_scope":"Layered Mount Sharp deposits, not every Gale Crater surface",
    "source":"NASA Mars Science Laboratory",
    "source_url":"https://ares.jsc.nasa.gov/missions/msl/"
  }
}

def rock_alignment(body:str,site_id:str,earth_units:list[dict])->dict:
    ref=REFERENCES.get(body+":"+site_id)
    if ref is None:
        return {"status":"planetary_geology_not_profiled","planetary_reference":None,
                "categorical_correspondence":None,
                "scientific_similarity_percent":None}
    expected=ref["expected_earth_lithology"]
    if not earth_units:
        state="no_mapped_earth_lithology"
        found=None
    else:
        labels=[]
        for unit in earth_units:
            if isinstance(unit,dict):
                for name in ("lith","name","strat_name","descrip"):
                    val=unit.get(name)
                    if isinstance(val,str):labels.append(val.lower())
        found=any(expected in text for text in labels)
        state="mapped_lithology_correspondence" if found else "mapped_lithology_not_same_category"
    return {
        "status":state,"categorical_correspondence":found,
        "expected_earth_lithology":expected,
        "planetary_reference":ref,
        "comparison_type":"Published NASA/USGS site lithology against Earth Macrostrat mapped lithology. Categorical reconnaissance only.",
        "limits":"A point geologic map class cannot certify whole-region mineralogy or Moon/Mars physical process equivalence.",
        "scientific_similarity_percent":None
    }
