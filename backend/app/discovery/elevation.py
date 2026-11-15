"""Sample real DEM elevations for user-selected Earth grid cells.

Only the returned point's elevation is observed/model-derived DEM data;
we do not assign that value to an entire geographic cell.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import math

import httpx

SOURCE_URL = 'https://api.open-meteo.com/v1/elevation'
SOURCE_NAME = 'Open-Meteo Elevation API / Copernicus DEM GLO-90 (2021)'
SOURCE_CITATION = 'https://doi.org/10.5270/ESA-c5d3d65'


def database_path() -> Path:
    specified = os.getenv('PLANETREX_DISCOVERY_DB')
    path = Path(specified) if specified else Path(__file__).resolve().parents[3] / 'data' / 'results' / 'discovery.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_observations(rows: list[dict]) -> None:
    with sqlite3.connect(database_path()) as connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS elevation_observations
            (latitude REAL NOT NULL, longitude REAL NOT NULL, elevation_m REAL,
             observed_at TEXT NOT NULL, source TEXT NOT NULL,
             PRIMARY KEY(latitude, longitude))''')
        connection.executemany('''INSERT OR REPLACE INTO elevation_observations
            (latitude,longitude,elevation_m,observed_at,source) VALUES (?,?,?,?,?)''', [
                (r['latitude'],r['longitude'],r['elevation_m'],r['retrieved_at'],SOURCE_NAME) for r in rows
            ])


async def sample_elevations(points: list[dict]) -> list[dict]:
    if not points:
        return []
    params = {
        'latitude': ','.join(str(point['latitude']) for point in points),
        'longitude': ','.join(str(point['longitude']) for point in points),
    }
    async with httpx.AsyncClient(timeout=22.0) as client:
        response = await client.get(SOURCE_URL, params=params)
        response.raise_for_status()
        data = response.json()
    heights = data.get('elevation')
    if not isinstance(heights, list) or len(heights) != len(points):
        raise ValueError('Elevation service returned an unexpected number of points')
    timestamp = datetime.now(timezone.utc).isoformat()
    result = []
    for point, height in zip(points, heights):
        if height is not None and (isinstance(height, bool) or not isinstance(height, (float, int)) or not math.isfinite(height)):
            raise ValueError('Elevation service returned a non-finite or invalid measurement')
        result.append({
            'latitude': point['latitude'], 'longitude': point['longitude'],
            'elevation_m': height, 'status': 'sampled' if height is not None else 'missing',
            'retrieved_at': timestamp,
            'provenance': {'source': SOURCE_NAME, 'url': SOURCE_URL,
                           'citation': SOURCE_CITATION, 'unit': 'm',
                           'method': 'DEM model sampled at cell center; not a cell-wide measurement'},
        })
    save_observations(result)
    return result


def stored_observations() -> list[dict]:
    """Return previously acquired observations; never invent missing measurements."""
    path = database_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS elevation_observations
            (latitude REAL NOT NULL, longitude REAL NOT NULL, elevation_m REAL,
             observed_at TEXT NOT NULL, source TEXT NOT NULL,
             PRIMARY KEY(latitude, longitude))''')
        rows = connection.execute('SELECT latitude, longitude, elevation_m, observed_at FROM elevation_observations ORDER BY observed_at DESC LIMIT 3000').fetchall()
    return [{'latitude':lat,'longitude':lon,'elevation_m':height,
             'status':'sampled' if height is not None else 'missing',
             'retrieved_at':when,
             'provenance': {'source': SOURCE_NAME, 'url': SOURCE_URL,
                            'citation': SOURCE_CITATION, 'unit': 'm',
                            'method': 'DEM model sampled at point; not a cell-wide measurement'}}
            for lat,lon,height,when in rows]
