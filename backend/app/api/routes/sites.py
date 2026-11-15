"""Documented navigation markers, NOT measured planetary analog reference profiles.

Landmark coordinates are planetocentric latitude and positive-east longitude.
These enable map navigation only. Scientific comparisons require independently
imported, source-backed reference profiles in the profile database.
"""
from typing import Literal
from fastapi import APIRouter

router = APIRouter(prefix='/exploration', tags=['Planetary navigation'])

MOON_SOURCE = 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html'
MARS_SOURCE = 'https://science.nasa.gov/mission/mars-2020-perseverance/location-map/'

def site(identifier: str, name: str, latitude: float, longitude: float,
         mission: str, source_url: str, kind: str = 'documented_landing_site') -> dict:
    return {'id': identifier, 'name': name, 'latitude': latitude,
            'longitude': longitude, 'mission': mission, 'source_url': source_url,
            'kind': kind, 'measured_reference_id': None,
            'similarity_percent': None}

SITES = {
    'moon': [
        site('apollo-11','Tranquility Base',0.67416,23.47314,'Apollo 11',MOON_SOURCE),
        site('apollo-12','Oceanus Procellarum',-3.0128,-23.4219,'Apollo 12',MOON_SOURCE),
        site('apollo-14','Fra Mauro',-3.64589,-17.47194,'Apollo 14',MOON_SOURCE),
        site('apollo-15','Hadley Rille',26.13239,3.63330,'Apollo 15',MOON_SOURCE),
        site('apollo-16','Descartes Highlands',-8.9734,15.5011,'Apollo 16',MOON_SOURCE),
        site('apollo-17','Taurus–Littrow',20.1911,30.7723,'Apollo 17',MOON_SOURCE),
        site('nobile-rim-1','Nobile Rim 1 (south polar reference)',-85.4381,37.36667,
             'Artemis candidate region · not a selected base',
             'https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf',
             'published_lunar_south_pole_candidate_reference'),
        site('malapert-massif','Malapert Massif (south polar reference)',-85.9948,-0.23578,
             'Artemis candidate region · not a selected base',
             'https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf',
             'published_lunar_south_pole_candidate_reference'),
    ],
    'mars': [
        site('perseverance','Jezero Crater',18.44463,77.45088,'Perseverance',
             'https://ntrs.nasa.gov/citations/20210024644'),
        site('curiosity','Gale Crater',-4.6,137.4,'Curiosity',
             'https://mars.nasa.gov/internal_resources/698/'),
        site('spirit','Gusev Crater',-14.57,175.47,'Spirit',
             'https://science.nasa.gov/mission/mer-spirit/'),
        site('insight','Elysium Planitia',4.5,135.62,'InSight',
             'https://science.nasa.gov/mission/insight/'),
    ],
}

@router.get('/sites')
def list_sites(body: Literal['moon','mars']) -> dict:
    """Show mapped mission landmarks for navigation; not analog candidates."""
    return {'body': body, 'sites': SITES[body], 'count': len(SITES[body]),
            'coordinate_convention': 'planetocentric_latitude_positive_east_longitude',
            'scientific_status': 'Navigation markers only; not measured references'}
