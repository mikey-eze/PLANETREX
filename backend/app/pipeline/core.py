"""Manual scientific terrain screening. Scores are distances, never fabricated percentages."""
from __future__ import annotations
import csv, json, math, os, sqlite3
from pathlib import Path
from datetime import datetime, timezone

FEATURES={"slope_deg":"degree","residual_roughness_m":"m"}
DEFAULT_SCALES={"slope_deg":5.0,"residual_roughness_m":20.0}

def db_location()->Path:
    return Path(os.environ.get("PLANETREX_PROFILE_DB") or Path(__file__).resolve().parents[3]/"data"/"results"/"profiles.sqlite3")

def connect(create:bool=True):
    p=db_location()
    if not create and not p.exists():return None
    p.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(p)
    db.row_factory=sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS profiles(
      id TEXT PRIMARY KEY, body TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
      name TEXT NOT NULL, crs TEXT NOT NULL, resolution_m REAL, source_url TEXT NOT NULL,
      source_product TEXT NOT NULL, source_version TEXT NOT NULL, retrieved_at TEXT NOT NULL,
      observation_kind TEXT NOT NULL, feature_json TEXT NOT NULL, quality_note TEXT NOT NULL DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_profiles_body ON profiles(body);
    CREATE TABLE IF NOT EXISTS processing_runs(
      run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,method TEXT NOT NULL,
      parameters TEXT NOT NULL,count_ok INTEGER NOT NULL,count_missing INTEGER NOT NULL);
    """)
    return db

def validate_profile(r:dict)->dict:
    required=("id","body","latitude","longitude","name","crs","source_url","source_product","source_version","retrieved_at","observation_kind","features")
    if any(k not in r for k in required):raise ValueError("Missing scientific profile fields")
    if r["body"] not in ("earth","moon","mars"):raise ValueError("Invalid body")
    lat,lon=float(r["latitude"]),float(r["longitude"])
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90<=lat<=90 and -180<=lon<=180):raise ValueError("Invalid coordinates")
    if r["body"]=="earth" and r["crs"]!="EPSG:4326":raise ValueError("Earth requires EPSG:4326")
    if r["body"]!="earth" and not str(r["crs"]).startswith(r["body"].upper()+":"):raise ValueError("Planetary CRS must be explicit")
    if r["observation_kind"] not in ("observed","modeled","derived"):raise ValueError("Invalid observation kind")
    for key in ("id","name","crs","source_url","source_product","source_version","retrieved_at"):
        if not isinstance(r[key],str) or not r[key].strip():raise ValueError("Missing provenance "+key)
    if not r["source_url"].startswith("https://"):raise ValueError("HTTPS source required")
    if not isinstance(r["features"],dict) or not r["features"]:raise ValueError("No feature measurements")
    if set(r["features"])-set(FEATURES):raise ValueError("Incomparable features")
    for name,reading in r["features"].items():
        if reading.get("unit")!=FEATURES[name]:raise ValueError("Incompatible feature unit")
        v=reading.get("value")
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError("Invalid feature value")
        u=reading.get("uncertainty")
        if u is not None and (isinstance(u,bool) or not isinstance(u,(float,int)) or not math.isfinite(u) or u<0):raise ValueError("Invalid uncertainty")
    return dict(r,latitude=lat,longitude=lon)

def save_profile(record:dict)->None:
    r=validate_profile(record)
    with connect() as db:
        db.execute("""INSERT OR REPLACE INTO profiles
        (id,body,latitude,longitude,name,crs,resolution_m,source_url,source_product,source_version,
        retrieved_at,observation_kind,feature_json,quality_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (r["id"],r["body"],r["latitude"],r["longitude"],r["name"],r["crs"],r.get("resolution_m"),
        r["source_url"],r["source_product"],r["source_version"],r["retrieved_at"],r["observation_kind"],
        json.dumps(r["features"]),r.get("quality_note","")))

def decode(row):
    result=dict(row);result["features"]=json.loads(result.pop("feature_json"));return result

def list_profiles(body:str,limit:int=100,offset:int=0)->list[dict]:
    db=connect(create=False)
    if db is None:return []
    with db:rows=db.execute("SELECT * FROM profiles WHERE body=? ORDER BY id LIMIT ? OFFSET ?",(body,limit,offset)).fetchall()
    return [decode(x) for x in rows]

def get_profile(profile_id:str):
    db=connect(create=False)
    if db is None:return None
    with db:row=db.execute("SELECT * FROM profiles WHERE id=?",(profile_id,)).fetchone()
    return decode(row) if row else None

def compare(reference:dict,candidate:dict,scales:dict|None=None):
    if reference["body"] not in ("moon","mars") or candidate["body"]!="earth":raise ValueError("Expected planetary reference and Earth candidate")
    if not all(k in reference["features"] and k in candidate["features"] for k in FEATURES):return None
    scales=DEFAULT_SCALES if scales is None else scales
    if set(scales)!=set(FEATURES) or any(not isinstance(v,(float,int)) or v<=0 or not math.isfinite(v) for v in scales.values()):raise ValueError("Invalid screening scales")
    diffs={}
    for key,unit in FEATURES.items():
        a=reference["features"][key];b=candidate["features"][key]
        delta=abs(a["value"]-b["value"])
        diffs[key]={"reference":a,"earth":b,"absolute_difference":round(delta,6),"normalized_difference":round(delta/scales[key],6),"scale":scales[key],"unit":unit}
    distance=sum(d["normalized_difference"] for d in diffs.values())/len(diffs)
    return {"reference_id":reference["id"],"earth_id":candidate["id"],
      "normalized_distance":round(distance,6),"feature_differences":diffs,"data_coverage":1.0,
      "similarity_percent":None,"scientific_status":"UNVALIDATED TERRAIN SCREENING; not a verified analog",
      "caveats":"Only local slope and residual roughness were compared"}

def search(reference_id:str,limit:int=50,offset:int=0,scales:dict|None=None)->dict:
    ref=get_profile(reference_id)
    if ref is None:raise LookupError("Reference profile not found")
    if ref["body"]=="earth":raise ValueError("Reference must be Moon or Mars")
    results=[r for earth in list_profiles("earth",100000,0) if (r:=compare(ref,earth,scales)) is not None]
    results.sort(key=lambda r:(r["normalized_distance"],r["earth_id"]))
    return {"reference":ref,"total_comparable":len(results),"results":results[offset:offset+limit],
      "limit":limit,"offset":offset,"scoring":"Unvalidated two-feature normalized distance; NOT a similarity percentage"}

def import_profiles_json(path:Path)->int:
    data=json.loads(path.read_text(encoding="utf-8"))
    records=data if isinstance(data,list) else data.get("profiles",[])
    for item in records:save_profile(item)
    return len(records)
