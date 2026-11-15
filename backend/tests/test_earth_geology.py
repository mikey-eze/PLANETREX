"""Safe parsing and API validation for sourced Earth geologic map units."""
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.earth_geology import parse_geology

client=TestClient(app)

def test_macrostrat_geologic_unit_parser():
    payload={"success":{"v":2,"data":[
        {"name":"mapped volcanic rocks","lith":"basalt","descrip":"lava flows",
         "source_id":123,"unsupported":{"nested":"metadata"}},
        {"name":"second mapped unit","liths":["basalt","andesite"]}
    ]}}
    units=parse_geology(payload)
    assert len(units)==2
    assert units[0]["lith"]=="basalt"
    assert "unsupported" not in units[0]
    assert units[0]["source_id"]==123

def test_macrostrat_empty_and_malformed_not_fabricated():
    assert parse_geology({"success":{"v":2,"data":[]}})==[]
    import pytest
    with pytest.raises(ValueError):
        parse_geology({"success":{"data":"incorrect"}})

def test_geology_api_rejects_bad_locations():
    assert client.get("/science/earth-geology?latitude=120&longitude=0").status_code==422
    assert client.get("/science/earth-geology?latitude=0&longitude=190").status_code==422

def test_geology_is_not_added_to_scientific_similarity_metric():
    r=client.get("/science/coverage")
    assert r.status_code==200
    geology=next(x for x in r.json()["dimensions"] if x["dimension"]=="geology_mineralogy")
    assert geology["paired_measurement_status"]=="not_yet_comparable"
