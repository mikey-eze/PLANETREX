"""Source-specific checks for PLANETREX Earth discovery beyond two DEM features.

Verify that *actual* NASA 2025 annual meteorology and Macrostrat geologic
mapping are present for Earth regions, and distinguish descriptive rock
correspondence from quantitatively calibrated planetary similarity.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.earth_discovery import read_field_profiles,rank_global
from app.api.routes.terrain_survey import read_dataset
from app.api.routes.earth_vegetation import parse_ndvi
from app.api.routes.planetary_context import rock_alignment

client=TestClient(app)


def test_earth_science_batch_has_real_annual_data_and_sources():
    d=read_field_profiles()
    assert d["ready"] is True, "Measured Earth science survey must be published"
    assert d["coverage"]["attempted_regions"]>=40
    assert d["coverage"]["with_annual_NASA_power"]>=20
    assert d["coverage"]["with_geologic_source_response"]>=20
    for p in d["profiles"]:
        power=p["earth_measurements"].get("power_annual",{})
        assert "errors" in p
        if power:
            for name in ("air_temperature_mean_c","precipitation_annual_mm",
                         "wind_10m_mean_ms","solar_shortwave_mean_kwh_m2_day"):
                x=power[name]
                assert x["source_url"].startswith("https://power.larc.nasa.gov")
                assert x["sample_days"]>=300
                assert x["period"]=="2025"
            solar=power["solar_shortwave_mean_kwh_m2_day"]
            if solar["value"] is not None:
                assert 0 <= solar["value"] < 15  # normalized kWh/m²/day, not raw MJ
        assert p["latitude"]<=90
        assert p["longitude"]<=180


def test_scan_exposes_all_earth_terrain_candidates():
    d=read_dataset()
    assert d
    ref,earth=rank_global(d,"mars","perseverance")
    assert ref["body"]=="mars"
    assert len(earth)>=100, "Do not restrict planetary analog search to ten famous locations"
    assert earth==sorted(earth,key=lambda x:(x["terrain_distance"],x["latitude"],x["longitude"]))
    assert all(x["scientific_similarity_percent"] is None for x in earth)


def test_dry_and_geology_filters_use_actual_sourced_evidence():
    dry=client.get("/science/earth-discovery",params={
        "body":"mars","site_id":"perseverance","environment":"dry","limit":100})
    assert dry.status_code==200
    data=dry.json()
    assert data["batch_earth_evidence_ready"] is True
    assert data["count"]>0
    assert data["total_measured_terrain_regions"]>=100
    assert all(x["earth_evidence"]["environment"]["precipitation_annual_mm"]["value"]<250
               for x in data["results"])
    mapped=client.get("/science/earth-discovery",params={
        "body":"moon","site_id":"apollo-15","environment":"geology","limit":100})
    assert mapped.status_code==200
    assert mapped.json()["count"]>0
    assert all(x["earth_evidence"]["geology_units"] for x in mapped.json()["results"])


def test_supported_site_geology_has_real_lithology_correspondence():
    for body,site,expected in [("mars","perseverance","sedimentary"),
                               ("moon","apollo-15","basalt")]:
        res=client.get("/science/earth-discovery",params={
            "body":body,"site_id":site,"environment":"lithology","limit":100})
        assert res.status_code==200
        d=res.json()
        assert d["count"]>0
        assert all(x["planetary_geology_evidence"]["categorical_correspondence"] is True
                   for x in d["results"])
        assert all(x["planetary_geology_evidence"]["expected_earth_lithology"]==expected
                   for x in d["results"])
        assert all(x["planetary_geology_evidence"]["scientific_similarity_percent"] is None
                   for x in d["results"])


def test_ndvi_quality_screen_discards_bad_pixels_and_snow():
    payload={"ncols":1,"nrows":1,"subset":[
        {"modis_date":"A2025001","band":"250m 16 days NDVI","data":[2500]},
        {"modis_date":"A2025001","band":"250m 16 days pixel reliability","data":[0]},
        {"modis_date":"A2025017","band":"250m 16 days NDVI","data":[8000]},
        {"modis_date":"A2025017","band":"250m 16 days pixel reliability","data":[3]},
        {"modis_date":"A2025033","band":"250m 16 days NDVI","data":[1000]},
        {"modis_date":"A2025033","band":"250m 16 days pixel reliability","data":[2]},
    ]}
    parsed=parse_ndvi(payload)
    assert parsed["ndvi_mean"]==0.25
    assert parsed["quality_accepted_samples"]==1
    assert parsed["rejected_or_missing_samples"]==2
    assert parsed["observed_snow_ice_quality_flags"]==1


def test_invalid_coordinates_and_no_fake_life_measurements():
    assert client.get("/science/earth-vegetation?latitude=89&longitude=10").status_code==422
    assert client.get("/science/earth-environmental-profile?latitude=92&longitude=3").status_code==422
    unmatched=rock_alignment("moon","nobile-rim-1",[{"lith":"basalt"}])
    assert unmatched["categorical_correspondence"] is None
    assert unmatched["scientific_similarity_percent"] is None
