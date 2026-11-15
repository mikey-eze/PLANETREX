"""Ensure science UI doesn't fabricate measurements, and sources are distinct.

No network requests: the NASA POWER response is replaced with sample raw data
and the Earth/Moon/Mars matching prototype is tested for truthful labeling.
"""
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.earth_measurements import _power, _observed

client = TestClient(app)


def test_screening_does_not_claim_physical_similarity():
    response = client.get("/science/analog-screening?body=mars&site_id=perseverance")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert all(row["scientific_similarity_percent"] is None for row in data["results"])
    assert all(row["tag_overlap_percent"] <= 100 for row in data["results"])


def test_unmeasured_site_returns_no_fabricated_score():
    response = client.get("/science/analog-screening?body=mars&site_id=insight")
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["status"] == "insufficient_site_evidence"


def test_measurement_endpoint_validates_geography():
    assert client.get("/science/earth-environment?latitude=99&longitude=0").status_code == 422
    assert client.get("/science/earth-environment?latitude=0&longitude=181").status_code == 422


def test_power_sentinel_values_not_treated_as_temperatures():
    assert _observed([-999, -9999, 21.0, 23.0, None, "20"]) == [21.0, 23.0]


def test_power_values_include_units_period_and_provenance():
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"properties": {"parameter": {
                "T2M": {"20250101": 10, "20250102": 20, "20250103": -999},
                "T2M_MAX": {"20250101": 30, "20250102": 32},
                "T2M_MIN": {"20250101": 5, "20250102": 7},
            }}}

    class Client:
        async def get(self, url, params):
            assert "power.larc.nasa.gov" in url
            assert params["start"] == "20250101"
            return Response()

    measurements = asyncio.run(_power(Client(), 19.4, -155.28))
    assert measurements["T2M"]["value"] == 15.0
    assert measurements["T2M"]["sample_days"] == 2
    assert measurements["T2M_MAX"]["value"] == 31.0
    assert measurements["T2M"]["unit"] == "°C"
    assert measurements["T2M"]["source"] == "NASA POWER"
