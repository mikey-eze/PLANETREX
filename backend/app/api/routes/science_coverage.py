"""Auditable status matrix across eight NASA challenge scientific dimensions.

'Source identified' never means 'measured feature validated'. Metadata/imagery
may be accessible, but only source-backed paired measurements may contribute to
a PLANETREX analog similarity distance.
"""
from __future__ import annotations
from fastapi import APIRouter
from app.api.routes.terrain_survey import read_dataset
from app.api.routes.mro_measured import read_mro
from app.api.routes.earth_discovery import read_field_profiles

router=APIRouter(prefix="/science",tags=["Scientific data completeness and coverage"])

SOURCES=[
 {"dimension":"topography","name":"Terrain, slope and surface relief",
  "earth":"NASA/METI ASTER GDEM v3 via Open Topo Data",
  "moon":"NASA LRO LOLA",
  "mars":"NASA MGS MOLA; USGS MRO CTX stereo DTMs",
  "source_urls":["https://svs.gsfc.nasa.gov/4720/",
                 "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
                 "https://stac.astrogeology.usgs.gov/docs/data/mars/ctxdtms/"],
  "next":"Validate paired DEM footprint, projected units and vertical uncertainty; high-resolution CTX is scene-only for now."},
 {"dimension":"geology_mineralogy","name":"Surface geology, lithology and mineralogy",
  "earth":"NASA Earthdata satellite data catalog; no validated paired lithology rasters",
  "moon":"LRO Diviner Christiansen feature and PDS geoscience products",
  "mars":"MRO CRISM spectral products",
  "source_urls":["https://pds-geosciences.wustl.edu/missions/lro/diviner.htm",
                 "https://pds-geosciences.wustl.edu/missions/mro/crism.htm"],
  "next":"Import georeferenced abundance/spectral rasters and validate common band/feature interpretation."},
 {"dimension":"temperature_illumination","name":"Temperature and illumination",
  "earth":"NASA POWER Earth climate + NASA MODIS/ORNL LST where quality-accepted",
  "moon":"LRO Diviner mapped thermal radiance and surface temperature",
  "mars":"Mars planetary thermal archives; temperature harmonization pending",
  "source_urls":["https://power.larc.nasa.gov/docs/services/api/",
                 "https://www.diviner.ucla.edu/data",
                 "https://pds-geosciences.wustl.edu/missions/lro/diviner.htm"],
  "next":"Import NASA Diviner and Mars thermal maps, align local time/season and sensor footprint before comparison."},
 {"dimension":"water_ice","name":"Water, ice and resources",
  "earth":"NASA POWER hydrology; NASA NSIDC snow and ice products",
  "moon":"LRO LEND / Mini-RF, Diviner polar resources; proxies are not ground-truth ice",
  "mars":"Orbiter spectral/radar resource evidence; not quantitative in current rankings",
  "source_urls":["https://nsidc.org/data/modis",
                 "https://pds-geosciences.wustl.edu/missions/lro/diviner.htm"],
  "next":"Import validated georeferenced polar/ice observations with explicit proxy uncertainty."},
 {"dimension":"aeolian","name":"Dust, wind and surface processes",
  "earth":"NASA POWER wind; Earth event and atmospheric archives",
  "moon":"Lunar regolith processes lack Earth-like atmospheric wind",
  "mars":"Orbiter atmospheric dust and sediment transport archives",
  "source_urls":["https://power.larc.nasa.gov/docs/services/api/",
                 "https://pds.nasa.gov/"],
  "next":"Quantify process similarity, not simply matching wind speed across different atmospheres."},
 {"dimension":"habitability","name":"Biology, extremophiles and habitability",
  "earth":"Earth ecological and microbial field observations not yet ingested",
  "moon":"No claimed lunar biology data",
  "mars":"No claimed evidence of Martian life",
  "source_urls":["https://search.earthdata.nasa.gov/"],
  "next":"Use documented Earth field studies; never infer extraterrestrial biology."},
 {"dimension":"subsurface","name":"Lava tubes, caves and subsurface geology",
  "earth":"Cave/lava tube geological surveys not yet ingested",
  "moon":"Potential cave/void observations require independent imaging verification",
  "mars":"Potential subsurface features require verified instruments and geospatial evidence",
  "source_urls":["https://pds.nasa.gov/"],
  "next":"Add validated cave feature catalog with uncertainty and geometry."},
 {"dimension":"engineering","name":"Landing, mobility, construction and mission operations",
  "earth":"Terrain proxies only; no engineering soil-strength tests",
  "moon":"Landing-base suitability requires far more than geomorphology",
  "mars":"Rover mobility and landing constraints not quantitatively processed",
  "source_urls":["https://science.nasa.gov/moon/",
                 "https://science.nasa.gov/mars/"],
  "next":"Add rover traverse, hazards, trafficability and field-testing evidence; prohibit declaring safe permanent bases."}
]

@router.get("/coverage")
def coverage()->dict:
    data=read_dataset()
    mro=read_mro()
    terrestrial=read_field_profiles()
    earth_profiles=terrestrial.get("profiles",[])
    measured_topography=bool(data and data.get("planetary_references") and
                             data.get("earth_terrain_profiles") and data.get("screenings"))
    rows=[]
    for source in SOURCES:
        is_topo=source["dimension"]=="topography"
        row={**source,
             "paired_measurement_status":("preliminary_measured_two_metric_screening"
                        if is_topo and measured_topography else "not_yet_comparable"),
             "scientific_similarity_percent":None,
             "validated_as_base_site":False}
        # Existing source-backed *terrestrial* observations may support mission
        # planning context even if no direct cross-planet physical metric exists.
        kinds={
          "topography":"NASA/METI ASTER regional elevation sampling",
          "geology_mineralogy":"Macrostrat point lithology and map-unit age",
          "temperature_illumination":"NASA POWER annual Earth T2M + surface shortwave; MODIS LST on demand",
          "water_ice":"NASA POWER annual precipitation (does not prove local ice)",
          "aeolian":"NASA POWER annual Earth wind speed (not Martian dust physics)",
          "habitability":"NASA MODIS NDVI on-demand (vegetation, not extraterrestrial life)",
          "subsurface":"No scientifically verified global cave/drillhole measurements",
          "engineering":"Terrain relief proxy only; no soil bearing-strength data"
        }
        row["earth_evidence_available"]=kinds.get(row["dimension"])
        row["earth_context_status"]="sourced_annual_Earth_climate_and_geology" if (
            earth_profiles and row["dimension"] in
            ("geology_mineralogy","temperature_illumination","water_ice","aeolian")) else (
            "sourced_terrain_context" if is_topo and measured_topography else
            "source_discovery_or_on_demand_only")
        rows.append(row)
    return {"status":"preliminary_research_system","dimensions":rows,
            "source_backed_earth_field_profiles":len(earth_profiles),
            "earth_profile_coverage":terrestrial.get("coverage",{}),
            "earth_conditions_from_NASA_POWER_2025":bool(earth_profiles),
            "earth_geology_source":"Macrostrat integrated geological maps",
            "planetary_geology_reference_sources":[
                "https://www.usgs.gov/publications/geologic-setting-apollo-15-samples",
                "https://science.nasa.gov/resource/detailed-panorama-of-mars-jezero-crater-delta/",
                "https://ares.jsc.nasa.gov/missions/msl/"
            ],
            "measured_comparable_dimensions":int(measured_topography),
            "total_planned_dimensions":len(SOURCES),
            "dimension_coverage_fraction":round(int(measured_topography)/len(SOURCES),3),
            "source_backed_global_terrain_scan":bool(measured_topography),
            "additional_high_resolution_mars_dtm_scene_count":(
                mro.get("measured_dtm_count",0) if mro else 0),
            "scientific_similarity_percent":None,
            "validated_full_multidimensional_analog_discoveries":0,
            "policy":"Dataset names, archive hits, and qualitative tags never constitute comparable physical measurements."}
