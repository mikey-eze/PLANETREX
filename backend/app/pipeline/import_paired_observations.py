"""Import independently verified measurement exports into PLANETREX.

Input CSV columns:
body,site_id,earth_id,side,domain,feature,value,unit,measurement_kind,
spatial_support_km,sampling_context,source_url

For each planetary reference / Earth region pair, import both planetary
and Earth observations from actual processed data products. No download
metadata or source URL alone is treated as a measurement.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from app.pipeline.paired_domain_scoring import FEATURES

FIELDS=("body","site_id","earth_id","side","domain","feature","value","unit",
        "measurement_kind","spatial_support_km","sampling_context","source_url")

def ingest(rows):
    output={"schema_version":1,"planetary":{},"earth":{},"import_report":{"accepted":0,"rejected":[]}}
    # Earth measurement records are shared by earth_id. Planetary records are
    # shared by body/site_id. Conflicting duplicates are rejected.
    for index,row in enumerate(rows,2):
        try:
            if not all(k in row for k in FIELDS):raise ValueError("missing_columns")
            if row["body"] not in ("moon","mars"):raise ValueError("invalid_body")
            if row["side"] not in ("planetary","earth"):raise ValueError("invalid_side")
            domain,feature=row["domain"],row["feature"]
            spec=FEATURES.get(domain,{}).get(feature)
            if spec is None:raise ValueError("unregistered_feature")
            if row["unit"]!=spec["unit"] or row["measurement_kind"]!=spec["kind"]:
                raise ValueError("unit_or_quantity_mismatch")
            value,support=float(row["value"]),float(row["spatial_support_km"])
            if not math.isfinite(value) or not math.isfinite(support) or support<=0:
                raise ValueError("invalid_number_or_support")
            if not row["source_url"].startswith("https://"):
                raise ValueError("invalid_provenance_url")
            if not row["site_id"] or not row["earth_id"]:
                raise ValueError("missing_site_identifier")
            key=f'{row["body"]}:{row["site_id"]}' if row["side"]=="planetary" else row["earth_id"]
            record={"value":value,"unit":row["unit"],"measurement_kind":row["measurement_kind"],
                    "spatial_support_km":support,"sampling_context":row["sampling_context"] or None,
                    "source_url":row["source_url"]}
            dest=output[row["side"]].setdefault(key,{}).setdefault(domain,{})
            if feature in dest and dest[feature]!=record:
                raise ValueError("conflicting_duplicate_measurement")
            dest[feature]=record
            output["import_report"]["accepted"]+=1
        except (ValueError,KeyError,TypeError) as exc:
            output["import_report"]["rejected"].append({"csv_line":index,"reason":str(exc)})
    return output

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[3]/"data"/"paired_observations.json")
    args=parser.parse_args()
    with args.input.open(newline="",encoding="utf-8") as source:
        result=ingest(csv.DictReader(source))
    if result["import_report"]["rejected"]:
        raise SystemExit(json.dumps(result["import_report"],indent=2))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(result["import_report"]))

if __name__=="__main__":main()
