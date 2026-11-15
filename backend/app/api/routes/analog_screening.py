"""Evidence-linked prototype feature-overlap screening.

This percentage is documented descriptive tag overlap, NOT physical similarity,
a validated scientific model or a prediction of exploration suitability.
"""
from fastapi import APIRouter, HTTPException
from typing import Literal

router=APIRouter(prefix="/science",tags=["Evidence-based analog screening"])
NASA_ANALOG="https://science.nasa.gov/solar-system/analog-explorer/"
NASA_ANALOGS="https://science.nasa.gov/solar-system/planetary-analogs/"
NASA_JEZERO="https://science.nasa.gov/resource/jezero-crater-mars-2020s-landing-site/"
NASA_GALE="https://science.nasa.gov/resource/sedimentation-and-erosion-in-gale-crater-mars/"
LPI_APOLLO="https://www.lpi.usra.edu/lunar/lunar_flyovers/apollo15/"
NASA_APOLLO="https://www.lpi.usra.edu/lunar/missions/apollo/apollo_15/samples/index.shtml"

# Evidence taxonomy: low-dimensional geology descriptions; not measured lab values.
TARGETS={
 "moon":{
  "apollo-11":{"name":"Tranquility Base · Apollo 11","tags":["basalt","volcanic"],"source":NASA_APOLLO},
  "apollo-12":{"name":"Oceanus Procellarum · Apollo 12","tags":["basalt","volcanic"],"source":NASA_APOLLO},
  "apollo-15":{"name":"Hadley Rille · Apollo 15","tags":["basalt","volcanic","rille"],"source":LPI_APOLLO},
 },
 "mars":{
  "perseverance":{"name":"Jezero Crater · Perseverance","tags":["sedimentary","delta","water_deposition","ancient_lake"],"source":NASA_JEZERO},
  "curiosity":{"name":"Gale Crater · Curiosity","tags":["sedimentary","ancient_lake","erosion"],"source":NASA_GALE},
 }
}
EARTH_SITES=[
 {"id":"kilauea","name":"Kīlauea basalt landscapes, Hawaii","latitude":19.4069,"longitude":-155.2834,
  "tags":["basalt","volcanic","active_lava"],"source":NASA_ANALOG,"bodies":["moon","mars"]},
 {"id":"holuhraun","name":"Holuhraun lava field, Iceland","latitude":64.852,"longitude":-16.829,
  "tags":["basalt","volcanic","lava_field"],"source":NASA_ANALOG,"bodies":["moon","mars"]},
 {"id":"mississippi-delta","name":"Mississippi River Delta, Louisiana","latitude":29.20,"longitude":-89.25,
  "tags":["sedimentary","delta","water_deposition","active_river"],"source":"https://science.nasa.gov/earth/earth-observatory/","bodies":["mars"]},
 {"id":"atacama","name":"Atacama Desert, Chile","latitude":-23.0,"longitude":-68.0,
  "tags":["arid","astrobiology"],"source":NASA_ANALOG,"bodies":["mars"]},
 {"id":"utah-canyonlands","name":"Utah canyonlands, United States","latitude":38.3269,"longitude":-109.8783,
  "tags":["sedimentary","erosion","arid"],"source":NASA_ANALOGS,"bodies":["mars"]},
]

@router.get("/analog-screening")
def analog_screening(body:Literal["moon","mars"],site_id:str)->dict:
    reference=TARGETS.get(body,{}).get(site_id)
    if not reference:
        return {"body":body,"site_id":site_id,"results":[],"count":0,"status":"insufficient_site_evidence",
         "message":"No curated geological descriptor profile for this landing site. A percent would be misleading.",
         "percent_meaning":"No percentage can be computed without referenced descriptors."}
    a=set(reference["tags"])
    results=[]
    for earth in EARTH_SITES:
        if body not in earth["bodies"]:continue
        b=set(earth["tags"]);shared=sorted(a&b);union=a|b
        if not shared:continue
        percent=round(100*len(shared)/len(union),1)
        results.append({
          "id":earth["id"],"name":earth["name"],"latitude":earth["latitude"],"longitude":earth["longitude"],
          "tag_overlap_percent":percent,"percentage_label":"Documented feature-tag overlap (prototype)",
          "matching_features":shared,"planetary_features":sorted(a),
          "earth_features":sorted(b),"unmatched_features":sorted(a^b),
          "overlap_fraction":f"{len(shared)}/{len(union)}",
          "reference_source_url":reference["source"],"earth_source_url":earth["source"],
          "scientific_similarity_percent":None,
          "status":"qualitative screening; not validated geophysical similarity"
        })
    results.sort(key=lambda x:(-x["tag_overlap_percent"],x["name"]))
    return {"body":body,"site_id":site_id,"reference":reference,"results":results,"count":len(results),
       "status":"preliminary_evidence_tag_screening",
       "percent_meaning":"Jaccard overlap = 100 × (shared documented geology tags / all distinct tags). This is a catalog-screening percentage, NOT physical similarity, habitability, or a scientifically calibrated analog score.",
       "limitations":["Hand-curated descriptions, not measured matched topographic/mineralogical parameter vectors.",
                      "Different environmental conditions across bodies are not considered.",
                      "Research verification and numeric scientific observations are required before a true similarity percentage can be reported."]}
