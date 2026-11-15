"""Deterministic, gap-free geographic tile generation (WGS84).

Tiles represent places to *investigate*, never confirmed planetary analogs.
The latitude/longitude grid is not equal-area; this is explicit in metadata.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bounds:
    south: float = -90.0
    north: float = 90.0
    west: float = -180.0
    east: float = 180.0

    def validate(self) -> None:
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError('Latitude bounds must satisfy -90 <= south < north <= 90')
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError('Longitude bounds must satisfy -180 <= west < east <= 180')


def make_grid(bounds: Bounds, step: float) -> list[dict]:
    """Generate all non-overlapping cells, clipping boundaries exactly."""
    bounds.validate()
    if not 0.25 <= step <= 45:
        raise ValueError('Cell size must be between 0.25 and 45 degrees')
    from math import ceil
    rows = ceil((bounds.north - bounds.south) / step - 1e-10)
    cols = ceil((bounds.east - bounds.west) / step - 1e-10)
    if rows * cols > 600:
        raise ValueError('Too many cells. Choose a larger cell size or a smaller geographic region (maximum 600).')
    cells = []
    for row in range(rows):
        south = round(bounds.south + row * step, 8)
        north = round(min(bounds.north, bounds.south + (row + 1) * step), 8)
        for col in range(cols):
            west = round(bounds.west + col * step, 8)
            east = round(min(bounds.east, bounds.west + (col + 1) * step), 8)
            center_lat = round((south + north) / 2, 8)
            center_lon = round((west + east) / 2, 8)
            cells.append({
                'id': f'{south:g}:{west:g}:{north:g}:{east:g}',
                'bounds': {'south': south, 'north': north, 'west': west, 'east': east},
                'latitude': center_lat, 'longitude': center_lon,
                'status': 'unassessed', 'elevation_m': None,
                'similarity_percent': None,
                'evidence': None,
            })
    return cells
