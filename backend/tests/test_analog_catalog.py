"""Regression tests for batch discovery, provenance, and non-fabrication."""
from app.pipeline.build_analog_catalog import build
from app.api.routes.deep_comparison import Observation, compare_observations, ComparisonRequest, deep_comparison

def test_catalog_uses_all_regions_and_preserves_missing_domains():
    terrain={"schema_version":1,"planetary_references":[{"body":"mars","id":"sample",
        "name":"sample","source_url":"https://pds.nasa.gov/",
        "stats":{"relief_m":100,"height_std_m":20}}],
        "earth_terrain_profiles":[{"id":"new_unclassified_location","name":"New site",
          "latitude":10,"longitude":20,"source_url":"https://www.opentopodata.org/",
          "stats":{"relief_m":110,"height_std_m":19,"coverage":1}}],
        "refined_earth_profiles":[]}
    earth={"schema_version":1,"profiles":[]}
    catalog=build(terrain,earth)
    row=catalog["results"]["mars:sample"]["candidates"][0]
    assert row["earth_id"]=="new_unclassified_location"
    assert row["previous_analog_certification_required"] is False
    assert row["paired_domains"]==1
    assert row["domains"]["water_ice"]["status"]=="unpaired"
    assert row["scientific_similarity_percent"] is None

def test_deep_comparison_rejects_air_vs_surface_temperature():
    planet=Observation(feature="temperature",value=-40,unit="°C",
        measurement_kind="surface_temperature",spatial_support_km=1,
        source_url="https://pds.nasa.gov/")
    earth=Observation(feature="temperature",value=20,unit="°C",
        measurement_kind="air_temperature",spatial_support_km=1,
        source_url="https://power.larc.nasa.gov/")
    result=compare_observations(planet,earth)
    assert result["status"]=="not_comparable"
    assert "different_measurement_kind" in result["reasons"]

def test_deep_comparison_only_counts_real_pairs():
    planet=Observation(feature="relief",value=100,unit="m",
        measurement_kind="regional_dem_relief",spatial_support_km=24,
        source_url="https://pds.nasa.gov/")
    earth=Observation(feature="relief",value=105,unit="m",
        measurement_kind="regional_dem_relief",spatial_support_km=24,
        source_url="https://www.opentopodata.org/")
    result=deep_comparison(ComparisonRequest(body="mars",planetary_site_id="sample",
        earth_latitude=10,earth_longitude=20,
        planetary={"topography":[planet]},earth={"topography":[earth]}))
    assert result["paired_domains"]==1
    assert result["paired_features"]==1
    assert result["scientific_similarity_percent"] is None
    assert result["domains"][3]["status"]=="unpaired"
