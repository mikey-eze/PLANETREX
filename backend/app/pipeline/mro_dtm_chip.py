"""MRO CTX DTM measured raster pilot (batch only).

Downloads small *overview windows* from NASA/USGS Cloud-Optimized GeoTIFFs
via HTTP range requests, never the entire enormous scene. Measurements refer
to the raster footprint, not automatically the exact rover landing location.

The resulting high-resolution summary is not mixed with MOLA 24-km screening
until planetary coordinate frames, footprint, and resolution are harmonized.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

STAC="https://stac.astrogeology.usgs.gov/api"
COLLECTION="mro_ctx_controlled_usgs_dtms"
LANDINGS={
    "perseverance":{"latitude":18.44463,"longitude":77.45088,"name":"Jezero Crater"},
    "curiosity":{"latitude":-4.6,"longitude":137.4,"name":"Gale Crater"},
}
MAX_DTM=2
MAX_SAMPLE=180


def bbox(lat,lon,half_width=1.5):
    return [lon-half_width,lat-half_width,lon+half_width,lat+half_width]


def stac_items(client,loc,limit=8):
    res=client.get(f"{STAC}/search",params={
        "collections":COLLECTION,"bbox":",".join(str(x) for x in bbox(loc["latitude"],loc["longitude"])),
        "limit":limit},timeout=24.0)
    res.raise_for_status()
    data=res.json()
    if data.get("type")!="FeatureCollection":
        raise ValueError("USGS STAC search did not yield FeatureCollection")
    products=[]
    for item in data.get("features",[]):
        asset=(item.get("assets") or {}).get("dtm") or {}
        uri=asset.get("href")
        if not isinstance(uri,str) or not uri.startswith("https://"):continue
        bb=item.get("bbox")
        if not isinstance(bb,list) or len(bb)<4:continue
        products.append({"id":item.get("id"),"asset_url":uri,"bbox":bb[:4],
            "stac_item_url":next((x["href"] for x in item.get("links",[])
                          if x.get("rel")=="self" and str(x.get("href","")).startswith("https://")),None)})
    return products


def raster_stats(dtm_uri):
    """Read a masked reduced-resolution COG, reject invalid/unreasonably large values."""
    import rasterio
    from rasterio.enums import Resampling
    env={
       "GDAL_DISABLE_READDIR_ON_OPEN":"EMPTY_DIR",
       "CPL_VSIL_CURL_ALLOWED_EXTENSIONS":".tif,.tiff",
       "GDAL_HTTP_MAX_RETRY":"2",
       "GDAL_HTTP_RETRY_DELAY":"1",
    }
    with rasterio.Env(**env):
        with rasterio.open(dtm_uri) as raster:
            if raster.count<1:
                raise ValueError("No bands in CTX DTM")
            # A representative downsample of the entire CTX scene is not a
            # 24km physical footprint and must not be scored as such.
            array=raster.read(1,out_shape=(min(raster.height,MAX_SAMPLE),
                    min(raster.width,MAX_SAMPLE)),resampling=Resampling.nearest,masked=True)
            values=np.ma.compressed(array).astype("float64")
            values=values[np.isfinite(values)&(np.abs(values)<100_000)]
            coverage=len(values)/array.size
            if coverage<0.15 or len(values)<100:
                raise ValueError("Insufficient valid elevation samples in CTX raster")
            p=np.percentile(values,[5,50,95])
            return {
              "nominal_post_spacing_m":20,
              "sampled_grid_shape":[int(x) for x in array.shape],
              "valid_sample_count":int(len(values)),
              "sample_count":int(array.size),
              "valid_pixel_fraction":round(float(coverage),4),
              "height_p05_m":round(float(p[0]),2),
              "height_median_m":round(float(p[1]),2),
              "height_p95_m":round(float(p[2]),2),
              "robust_relief_p95_p05_m":round(float(p[2]-p[0]),2),
              "height_std_sample_m":round(float(np.std(values)),2),
              "raster_width":int(raster.width),"raster_height":int(raster.height),
              "crs":str(raster.crs) if raster.crs else None,
              "map_bounds":[round(float(x),3) for x in raster.bounds],
              "sampled_footprint":"entire DTM scene as nearest-neighbor 180x180 overview; not the 24km planetary comparison window",
              "vertical_quality":"not calibrated against MOLA control/QA files; scene-wide overview is not reliable for landing-hazard decisions",
            }


def produce(output:Path):
    report={"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
      "source":"NASA / USGS MRO CTX controlled stereo Digital Terrain Models",
      "collection":COLLECTION,"source_url":"https://stac.astrogeology.usgs.gov/docs/data/mars/ctxdtms/",
      "status":"batch_high_resolution_context_only","used_in_analog_scoring":False,
      "sites":[],"warnings":[
        "DTM scenes may be near but not contain the exact rover landing point.",
        "Only source raster height overview is sampled; check CTX-MOLA QA, artifacts and georeferencing before quantitative comparisons.",
        "MRO CTX 20m grid post spacing is not equivalent to true spatial resolution or 24km regional MOLA/ASTER sample footprint."
      ]}
    with httpx.Client(follow_redirects=True,timeout=28.0) as client:
      for site_id,loc in LANDINGS.items():
        row={"site_id":site_id,"site_name":loc["name"],"latitude":loc["latitude"],
             "longitude":loc["longitude"],"dtms":[],"errors":[]}
        try:
          products=stac_items(client,loc)
          for product in products[:MAX_DTM]:
            try:
              stats=raster_stats(product["asset_url"])
              row["dtms"].append({**product,"measurement":stats,"status":"measured_scene_overview",
                  "planet":"Mars","unit":"m","source_processing":"NASA/USGS CTX stereo aligned to MOLA"})
            except Exception as exc:
              row["errors"].append({"id":product["id"],"type":type(exc).__name__,
                                    "message":str(exc)[:220]})
        except Exception as exc:
          row["errors"].append({"type":type(exc).__name__,"message":str(exc)[:220]})
        report["sites"].append(row)
    report["measured_dtm_count"]=sum(len(s["dtms"]) for s in report["sites"])
    if report["measured_dtm_count"]==0:
      # No fake data; workflow still publishes its diagnostic to explain why.
      report["status"]="raster_measurements_unavailable"
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(".tmp")
    temp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    temp.replace(output)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=produce(args.output)
    print(json.dumps({"status":report["status"],"measured_dtm_count":report["measured_dtm_count"],
      "errors":[{"id":x["site_id"],"errors":x["errors"]} for x in report["sites"]]}))


if __name__=="__main__":
    main()
