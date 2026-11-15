"""Evidence-safe geographic grid and read-only stored observations."""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.discovery.grid import Bounds, make_grid
from app.discovery.elevation import stored_observations

router = APIRouter(prefix='/discovery', tags=['Geographic screening'])


@router.get('/grid')
def geographic_grid(
    step: Annotated[float, Query(ge=0.25, le=45)] = 30,
    south: float = -90, north: float = 90,
    west: float = -180, east: float = 180,
) -> dict:
    try:
        cells = make_grid(Bounds(south=south, north=north, west=west, east=east), step)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        'cells': cells, 'count': len(cells), 'target': 'earth',
        'coordinate_system': 'WGS84 latitude/longitude; angular cells are not equal-area',
        'status': 'unassessed',
        'method': 'Exhaustive geographic tiling; not planetary analog discovery or classification',
        'coverage': 'All Earth coordinates in supplied bounds, including ocean',
    }


@router.get('/observations')
def observations() -> dict:
    """Local reproducible record of previously queried point elevations."""
    rows = stored_observations()
    return {'samples': rows, 'count': len(rows), 'similarity_percent': None}
