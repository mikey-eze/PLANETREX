"""Batch-only NASA LOLA + NASA MOLA vs global Earth ASTER terrain screening.

Inputs are **real elevation rasters** and ASTER GDEM point samples. The resulting
distance is ONLY a comparison of window-scale topographic relief, not a
calibrated % similarity, geology match, or base suitability recommendation.

Run: python -m app.pipeline.terrain_batch --output ../data/terrain_survey.json
Job is finite and rate-limited; the website only reads its persisted JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev

import httpx
import numpy as np
import tifffile

LOLA_URL = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_4.tif"
LOLA_INFO = "https://svs.gsfc.nasa.gov/4720/"
MOLA_URL = "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg004/megt90n000cb.img"
MOLA_INFO = "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html"
EARTH_URL = "https://api.opentopodata.org/v1/aster30m"
EARTH_INFO = "https://www.opentopodata.org/datasets/aster/"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"

# Established/approximate planetocentric navigation coordinates; not new landing site recommendations.
TARGET_SITES = [
    {"id": "apollo-11", "body": "moon", "name": "Tranquility Base", "lat": 0.67416, "lon": 23.47314},
    {"id": "apollo-15", "body": "moon", "name": "Hadley Rille", "lat": 26.13239, "lon": 3.63330},
    {"id": "apollo-17", "body": "moon", "name": "Taurus–Littrow", "lat": 20.1911, "lon": 30.7723},
    {"id": "nobile-rim-1", "body": "moon", "name": "Nobile Rim 1 · NASA south-polar region reference",
     "lat": -85.4381, "lon": 37.36667,
     "coordinate_source": "https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf"},
    {"id": "malapert-massif", "body": "moon", "name": "Malapert Massif · NASA south-polar region reference",
     "lat": -85.9948, "lon": -0.23578,
     "coordinate_source": "https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf"},
    {"id": "perseverance", "body": "mars", "name": "Jezero Crater", "lat": 18.44463, "lon": 77.45088},
    {"id": "curiosity", "body": "mars", "name": "Gale Crater", "lat": -4.6, "lon": 137.4},
    {"id": "insight", "body": "mars", "name": "Elysium Planitia", "lat": 4.5, "lon": 135.62},
]
RADIUS_M = {"earth": 6371000.0, "moon": 1737400.0, "mars": 3389500.0}
WINDOW_RADIUS_KM = 12.0
# Approximate 8-point ring at consistent physical offsets: center + N E S W + diagonals.
OFFSETS = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1),
           (0.7071068, 0.7071068), (-0.7071068, 0.7071068),
           (0.7071068, -0.7071068), (-0.7071068, -0.7071068)]


def surroundings(body: str, lat: float, lon: float):
    radius = RADIUS_M[body]
    delta_lat = math.degrees(WINDOW_RADIUS_KM * 1000 / radius)
    coslat = max(0.005, abs(math.cos(math.radians(lat))))
    return [(max(-89.8, min(89.8, lat + dy * delta_lat)),
             ((lon + dx * delta_lat / coslat + 180) % 360) - 180)
            for dy, dx in OFFSETS]


def terrain_stats(values: list[float | None]) -> dict | None:
    if len(values) != 9:
        raise ValueError("Nine elevation points required")
    valid = [v for v in values if v is not None and math.isfinite(v)]
    if len(valid) < 8 or values[0] is None:
        return None
    # Remove the datum: only use differences over a 24-km diameter window.
    return {"relief_m": round(max(valid) - min(valid), 1),
            "height_std_m": round(pstdev(valid), 1),
            "coverage": round(len(valid) / len(values), 3),
            "sample_count": len(valid), "window_radius_km": WINDOW_RADIUS_KM}


def fetch_binary(client: httpx.Client, url: str, path: Path) -> dict:
    if not path.exists() or path.stat().st_size < 100_000:
        path.parent.mkdir(parents=True, exist_ok=True)
        with client.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with path.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"url": url, "sha256": digest, "file_bytes": path.stat().st_size}


def load_lola(path: Path) -> np.ndarray:
    # NASA SVS 4ppd geocentric cylindrical LOLA: float32 elevation relative to 1737.4km sphere, in km.
    data = tifffile.imread(path)
    if data.shape != (720, 1440):
        raise ValueError(f"LOLA shape is unexpected: {data.shape}")
    if not np.issubdtype(data.dtype, np.floating):
        raise ValueError("LOLA float raster expected: do not guess a pixel conversion")
    return np.asarray(data, dtype=np.float32) * 1000.0


def load_mola(path: Path) -> np.ndarray:
    # NASA PDS MOLA 4ppd MEGDR topography: 16-bit big endian integer elevations in meters.
    # Ref: PDS MEGDR SIS; must verify label dimensions/bytes and topography product identity.
    size = 720 * 1440 * 2
    if path.stat().st_size != size:
        raise ValueError(f"MOLA binary file unexpected size: {path.stat().st_size}; expected {size}")
    return np.fromfile(path, dtype=">i2").reshape(720, 1440)


def sample_global(array: np.ndarray, lat: float, lon: float, body: str) -> float | None:
    if array.shape != (720, 1440):
        raise ValueError("Expected 4 pixels/degree global raster")
    row = min(719, max(0, int((90.0 - lat) * 4)))
    # NASA LOLA centered at longitude 0 (−180..180); MOLA starts at 0°E.
    x = (lon + 180) % 360 if body == "moon" else lon % 360
    col = min(1439, max(0, int(x * 4)))
    height = int(array[row, col]) if body == "mars" else float(array[row, col])
    # MOLA invalid/no-data sentinel generally -32768; guard conservative.
    if not math.isfinite(height) or height <= -32000:
        return None
    return float(height)


def planet_profiles(lola: np.ndarray, mola: np.ndarray):
    results = []
    for target in TARGET_SITES:
        arr = lola if target["body"] == "moon" else mola
        coords = surroundings(target["body"], target["lat"], target["lon"])
        vals = [sample_global(arr, lat, lon, target["body"]) for lat, lon in coords]
        stats = terrain_stats(vals)
        if stats is None:
            continue
        results.append({
            **target, "stats": stats,
            "method": "9 approximately geodesic sampled elevations in a 12km-radius disk; nearest DEM pixels. Polar area geometry is approximate.",
            "source_url": LOLA_INFO if target["body"] == "moon" else MOLA_INFO,
            "dataset": "LRO LOLA NASA SVS ldem_4 (4 ppd)" if target["body"] == "moon" else "MGS MOLA MEGDR topography (4 ppd)",
            "horizontal_sampling_deg": 0.25, "unit": "m",
            "status": "measured/model-derived regional DEM screening; coarse resolution"
        })
    return results


def earth_grid():
    # Equal-degree global candidate survey, NOT uniform area coverage, not a true land mask.
    # High polar regions excluded as ASTER GDEM stops ~83° latitude.
    return [(lat, lon) for lat in range(-75, 76, 15) for lon in range(-170, 171, 20)]


def fetch_earth_windows(client: httpx.Client, grid: list[tuple[int, int]]):
    all_points = [(lat, lon, surroundings("earth", lat, lon)) for lat, lon in grid]
    flat = [point for _, _, points in all_points for point in points]
    heights: list[float | None] = []
    # Public server limit 100 locations/call and ~1 request/sec. 80 points/request.
    for start in range(0, len(flat), 80):
        chunk = flat[start:start + 80]
        params = {"locations": "|".join(f"{a:.5f},{b:.5f}" for a,b in chunk)}
        response = client.get(EARTH_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results")
        if payload.get("status") != "OK" or not isinstance(rows, list) or len(rows) != len(chunk):
            raise ValueError(f"Earth DEM response invalid in chunk {start // 80}")
        for record in rows:
            value = record.get("elevation")
            heights.append(float(value) if isinstance(value, (int,float)) and math.isfinite(value) else None)
        time.sleep(1.25)
    candidates = []
    for i, (lat, lon, _) in enumerate(all_points):
        stats = terrain_stats(heights[i * 9:(i + 1) * 9])
        if stats is None: continue
        candidates.append({
            "id": f"earth_{lat:+03d}_{lon:+04d}",
            "name": f"Global candidate grid: {abs(lat)}°{'N' if lat >= 0 else 'S'}, {abs(lon)}°{'E' if lon >= 0 else 'W'}",
            "latitude": lat, "longitude": lon, "stats": stats,
            "source_url": EARTH_INFO, "dataset": "NASA/METI ASTER GDEM v3 via Open Topo Data",
            "kind": "global grid cell center with 9 terrain samples", "source_measurement_unit": "m",
            "footprint_km": 24, "validation": "Unverified land classification; needs follow-up imagery and material evidence"
        })
    return candidates, {"grid_cells_attempted": len(grid), "cells_with_terrain_coverage": len(candidates),
                        "points_attempted": len(flat), "nonempty_point_samples": sum(x is not None for x in heights),
                        "grid_step_lat_deg": 15, "grid_step_lon_deg": 20,
                        "sampling_warning": "Global degree grid over ASTER coverage; not equal-area; no explicit land mask. Ocean/void and low coverage excluded by sample availability."}


def distance(ref: dict, candidate: dict) -> dict:
    a, b = ref["stats"], candidate["stats"]
    # Log ratios remain dimensionless, treat smooth and rugged regions symmetrically.
    relief = abs(math.log1p(a["relief_m"]) - math.log1p(b["relief_m"]))
    roughness = abs(math.log1p(a["height_std_m"]) - math.log1p(b["height_std_m"]))
    return {
        "terrain_distance": round(0.6 * relief + 0.4 * roughness, 4),
        "distance_terms": {"log1p_relief_absolute_difference": round(relief,4),
                           "log1p_std_absolute_difference": round(roughness,4)},
        "measured_terrain_features": 2, "requested_features": 8,
        "measured_dimensions": 1, "planned_dimensions": 8,
        "dimension_coverage_fraction": 0.125,
        "scientific_similarity_percent": None,
        "physical_match_is_validated": False,
    }


def produce(output: Path, cache_dir: Path = CACHE_DIR) -> dict:
    with httpx.Client(timeout=50, follow_redirects=True) as client:
        lola_path = cache_dir / "lola_4ppd.tif"
        mola_path = cache_dir / "mola_4ppd.img"
        source_lola = fetch_binary(client, LOLA_URL, lola_path)
        source_mola = fetch_binary(client, MOLA_URL, mola_path)
        refs = planet_profiles(load_lola(lola_path), load_mola(mola_path))
        if not any(r["body"] == "moon" for r in refs) or not any(r["body"] == "mars" for r in refs):
            raise ValueError("Missing valid lunar or Martian source raster reference profiles")
        earth, survey = fetch_earth_windows(client, earth_grid())
    if len(earth) < 5:
        raise ValueError("Too few actual measured Earth grid windows; refusing empty scientific result")
    screenings = {}
    for ref in refs:
        rows = []
        for candidate in earth:
            result = distance(ref, candidate)
            rows.append({**candidate, **result})
        rows.sort(key=lambda r: r["terrain_distance"])
        screenings[ref["body"] + ":" + ref["id"]] = rows[:15]
    package = {
        "schema_version": 1, "built_at": datetime.now(timezone.utc).isoformat(),
        "scientific_status": "coarse_global_topographic_survey_only",
        "score_definition": "0.6*|log(1+relief_planet) - log(1+relief_earth)| + 0.4*|log(1+height_std_planet) - log(1+height_std_earth)|; smaller is closer",
        "explanation": "Actual regional DEM-derived relative relief and vertical spread over a 24km diameter footprint. Different DEM resolutions, planetary geodesy and source quality limit comparability. No site is confirmed as a validated planetary analog.",
        "nasa_datasets": {
            "moon": {**source_lola, "description": "LOLA lunar global DEM, meters of elevation relative to lunar datum"},
            "mars": {**source_mola, "description": "MOLA global MEGDR topography relative to areoid"}
        },
        "earth_dataset": {"name": "ASTER GDEM v3", "endpoint": EARTH_URL,
                          "source_url": EARTH_INFO, "provenance": "NASA/METI global DEM ~30m via OpenTopoData"},
        "global_scan": survey, "planetary_references": refs,
        "earth_terrain_profiles": earth, "screenings": screenings,
        "limitations": [
            "No material or mineral measurements in score, no water/ice or thermal matching, no habitat or base suitability prediction.",
            "The ASTER GDEM and planetary rasters have different horizontal resolution and different datums; only within-window variation is considered.",
            "Only a 15°×20° degree grid was screened, and land/biome classification is not yet independently verified.",
            "Footprint has 9 discrete samples, not area-complete terrain statistics; results are candidate leads only.",
            "Uncertainty is not yet quantified; no physical similarity % is shown."
        ]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    temp.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(output)
    return package


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[3] / "data" / "terrain_survey.json")
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    args = parser.parse_args()
    result = produce(args.output, args.cache_dir)
    print(json.dumps({"output": str(args.output), "planetary_sites": len(result["planetary_references"]),
                      "scanned": result["global_scan"]["grid_cells_attempted"],
                      "earth_with_data": result["global_scan"]["cells_with_terrain_coverage"]}))


if __name__ == "__main__":
    main()
