"""Measured-science regression tests against the committed batch artifact."""
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.terrain_survey import read_dataset

client=TestClient(app)


def test_reproducible_dem_batch_is_present():
    data=read_dataset()
    assert data is not None, "Scientific batch must be committed before deployment"
    assert data["scientific_status"] == "coarse_to_fine_two_feature_topographic_screening"
    assert data["refinement"]["attempted_cells"] >= 8
    assert data["refinement"]["usable_cells"] >= 8
    assert data["global_scan"]["grid_cells_attempted"] >= 100
    assert data["global_scan"]["cells_with_terrain_coverage"] >= 5
    assert data["nasa_datasets"]["moon"]["sha256"]
    assert data["nasa_datasets"]["mars"]["sha256"]


def test_measured_moon_and_mars_candidate_endpoints():
    for body, site in [("moon","apollo-15"),("mars","perseverance")]:
        res=client.get(f"/science/terrain-survey/candidates?body={body}&site_id={site}")
        assert res.status_code == 200
        payload=res.json()
        assert payload["ready"]
        assert payload["reference"]["body"] == body
        assert len(payload["results"]) >= 2
        distances=[r["terrain_distance"] for r in payload["results"]]
        assert distances == sorted(distances)
        assert any(x.get("search_stage") == "coarse_to_fine_refinement" for x in payload["results"])
        assert all(r["scientific_similarity_percent"] is None for r in payload["results"])
        assert all(r["measured_terrain_features"] == 2 for r in payload["results"])
        assert all(r["stats"]["sample_count"] >= 8 for r in payload["results"])


def test_reject_physical_percent_and_unknown_reference():
    res=client.get("/science/terrain-survey/candidates?body=mars&site_id=fake")
    assert res.status_code == 200
    assert res.json()["count"] == 0
    assert res.json()["scientific_similarity_percent"] is None


def test_source_coherence():
    data=read_dataset()
    assert "ldem_4.tif" in data["nasa_datasets"]["moon"]["url"]
    assert "megt90n000cb.img" in data["nasa_datasets"]["mars"]["url"]
    assert "aster30m" in data["earth_dataset"]["endpoint"]
    refs=data["planetary_references"]
    assert sum(p["body"]=="moon" for p in refs) > 0
    assert sum(p["body"]=="mars" for p in refs) > 0
