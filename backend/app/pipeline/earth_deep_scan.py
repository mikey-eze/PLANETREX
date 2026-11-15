"""Source-backed annual Earth field survey of systematically discovered regions.

NOT a planetary climate or life similarity score. NASA POWER 2025,
Macrostrat geological units and selected quality-controlled NASA MODIS
land-surface temperature/NDVI products. Missing providers are explicit.
The machine-readable output is stored and served without recomputation.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import math
import time
from datetime import datetime,timezone
from pathlib import Path
import httpx

from app.api.routes.earth_geology import parse_geology,MACROSTRAT
from app.api.routes.earth_surface import fetch_surface
from app.api.routes.earth_vegetation import fetch_ndvi

POWER="https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS=("T2M","T2M_MAX","T2M_MIN","PRECTOTCORR","WS10M","ALLSKY_SFC_SW_DWN")
YEAR="2025"
PARAM_META={
 "T2M":("air_temperature_mean_c","°C","mean"),
 "T2M_MAX":("air_temperature_mean_daily_high_c","°C","mean"),
 "T2M_MIN":("air_temperature_mean_daily_low_c","°C","mean"),
 "PRECTOTCORR":("precipitation_annual_mm","mm/year","sum"),
 "WS10M":("wind_10m_mean_ms","m/s","mean"),
 "ALLSKY_SFC_SW_DWN":("solar_shortwave_mean_kwh_m2_day","kWh/m²/day","mean"),
}

def select_candidates(survey:dict,max_points:int=70)->list[dict]:
    """Top leads from EVERY planetary site + some spatially dispersed samples."""
    chosen={}
    for rows in survey.get("screenings",{}).values():
        for row in rows[:10]:
            chosen.setdefault(row["id"],row)
    # Include a diversity sample from all already measured global grid cells.
    for row in sorted(survey.get("earth_terrain_profiles",[]),
                      key=lambda x:(abs(x["latitude"]),abs(x["longitude"])),reverse=True):
        if len(chosen)>=max_points:break
        chosen.setdefault(row["id"],row)
    return list(chosen.values())[:max_points]

def sum_source_power(payload:dict)->dict:
    params=payload.get("properties",{}).get("parameter",{})
    if not isinstance(params,dict) or not params:
        raise ValueError("NASA POWER delivered no measurements")
    fields={}
    for name,(field,unit,kind) in PARAM_META.items():
        series=params.get(name)
        if not isinstance(series,dict):
            fields[field]={"value":None,"unit":unit,"sample_days":0,"status":"no_source_data"}
            continue
        dates=[(k,float(v)) for k,v in series.items()
               if isinstance(k,str) and k.startswith(YEAR)
               and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>-900]
        value=round(sum(v for _,v in dates) if kind=="sum" else sum(v for _,v in dates)/len(dates),3) if dates else None
        fields[field]={"value":value,"unit":unit,"sample_days":len(dates),
                       "status":"source_derived" if value is not None else "no_source_data",
                       "source":"NASA POWER daily", "source_url":POWER, "period":YEAR,
                       "aggregation":kind}
    return fields

def fetch_power(lat:float,lon:float)->dict:
    with httpx.Client(timeout=44,follow_redirects=True) as client:
        r=client.get(POWER,params={
            "latitude":lat,"longitude":lon,"community":"AG",
            "parameters":",".join(PARAMS),
            "start":"20250101","end":"20251231","format":"JSON",
        })
        r.raise_for_status()
        return sum_source_power(r.json())

def fetch_geology(lat:float,lon:float)->dict:
    with httpx.Client(timeout=20,follow_redirects=True) as client:
        r=client.get(MACROSTRAT,params={"lat":lat,"lng":lon,"response":"long"})
        r.raise_for_status()
        mapped=parse_geology(r.json())
    return {"status":"mapped" if mapped else "not_mapped","units":mapped,
            "source_url":MACROSTRAT,"source":"Macrostrat integrated geological maps",
            "measurement_kind":"Mapped regional geological unit at Earth point, scale varies"}

def collect_region(region:dict)->dict:
    lat,lon=round(float(region["latitude"]),4),round(float(region["longitude"]),4)
    data={"id":region["id"],"latitude":lat,"longitude":lon,
          "terrain":{"relief_m":region["stats"]["relief_m"],
                     "height_std_m":region["stats"]["height_std_m"],
                     "source_url":region["source_url"]},
          "earth_measurements":{}, "errors":[],
          "source_status":{}}
    for label,fn in (("power_annual",fetch_power),("geology",fetch_geology)):
        try:
            data["earth_measurements"][label]=fn(lat,lon)
            data["source_status"][label]="sourced"
        except Exception as exc:
            data["source_status"][label]="unavailable"
            data["errors"].append({"source":label,"type":type(exc).__name__})
        time.sleep(.15)
    # Earth-only descriptive science tags derived from source measurements.
    # They are NOT absolute suitability or direct lunar/Martian similarity.
    tags=[]
    power=data["earth_measurements"].get("power_annual",{})
    precip=power.get("precipitation_annual_mm",{}).get("value")
    air_temp=power.get("air_temperature_mean_c",{}).get("value")
    wind=power.get("wind_10m_mean_ms",{}).get("value")
    if precip is not None and precip < 250:tags.append("low_annual_precipitation")
    if precip is not None and precip >= 1000:tags.append("high_annual_precipitation")
    if air_temp is not None and air_temp < 0:tags.append("cold_annual_mean")
    if air_temp is not None and air_temp > 25:tags.append("warm_annual_mean")
    if wind is not None and wind > 6:tags.append("windy_annual_mean")
    if data["source_status"].get("geology")=="sourced" and data["earth_measurements"]["geology"]["units"]:
        tags.append("mapped_geology_available")
    if region["stats"]["relief_m"]>=1000:tags.append("high_local_relief")
    data["earth_conditions"]=tags
    data["earth_measurements"]["source_count"]=sum(v=="sourced" for v in data["source_status"].values())
    return data

def make_survey(source:Path,output:Path,max_points:int=70,workers:int=3)->dict:
    terrain=json.loads(source.read_text(encoding="utf-8"))
    selected=select_candidates(terrain,max_points=max_points)
    if len(selected)<5:raise ValueError("No terrestrial terrain candidates found")
    profiles=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4,max(1,workers))) as pool:
        pending={pool.submit(collect_region,row):row["id"] for row in selected}
        for future in concurrent.futures.as_completed(pending):
            profiles.append(future.result())
            print(json.dumps({"completed":len(profiles),"total":len(selected),
              "candidate":pending[future],"sources":profiles[-1]["source_status"]}),flush=True)
    profiles.sort(key=lambda x:x["id"])
    sourced_power=sum(x["source_status"].get("power_annual")=="sourced" for x in profiles)
    sourced_geology=sum(x["source_status"].get("geology")=="sourced" for x in profiles)
    if sourced_power<5:
        raise RuntimeError("Insufficient real NASA POWER profiles; refuse to publish empty/fabricated dataset")
    result={
      "schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
      "kind":"Earth-only multi-source environment evidence for potential Moon/Mars analog discovery",
      "selection_method":"Union of top 10 terrain candidates for each planetary reference, plus geographically dispersed surveyed Earth regions",
      "data_sources":{
          "terrain":"NASA/METI ASTER GDEM v3 via Open Topo Data",
          "atmosphere_water_solar":"NASA POWER daily 2025",
          "geology":"Macrostrat integrated terrestrial geologic map"
      },
      "source_count":{"annual_power":sourced_power,"geology":sourced_geology},
      "coverage":{"attempted_regions":len(profiles),"with_annual_NASA_power":sourced_power,
                  "with_geologic_source_response":sourced_geology},
      "interpretation":"Annual Earth observations and geology context, not yet a calibrated eight-dimensional Moon/Mars distance",
      "missing_paired_reference_dimensions":["mineral abundance","planetary surface temperature vs Earth LST",
          "planetary water/ice","dust physical processes","biology","subsurface","engineering soil strength"],
      "scientific_similarity_percent":None,
      "profiles":profiles,
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(output)
    print(json.dumps(result["coverage"]),flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=Path(__file__).resolve().parents[3]/"data"/"terrain_survey.json")
    p.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[3]/"data"/"earth_science_profiles.json")
    p.add_argument("--max-points",type=int,default=65)
    args=p.parse_args()
    make_survey(args.input,args.output,args.max_points)

if __name__=="__main__":main()
