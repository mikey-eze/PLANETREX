"""MRO metadata validation and paired DEM evidence regression checks."""
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.mro_context import query_bbox, parse_items
from app.api.routes.terrain_survey import read_dataset

client=TestClient(app)


def test_mro_stac_parser_rejects_records_missing_dtm_asset():
    payload={"type":"FeatureCollection","features":[
        {"id":"good","properties":{"title":"MRO controlled CTX DTM"},
         "assets":{"dtm":{"href":"https://example.org/data.tif"}},
         "links":[{"rel":"self","href":"https://example.org/item"}]},
        {"id":"not_dtm","properties":{"title":"Just an image"},
         "assets":{"browse":{"href":"https://example.org/image.jpg"}}},
    ]}
    records=parse_items(payload,5)
    assert len(records)==1
    assert records[0]["id"]=="good"
    assert records[0]["nominal_post_spacing_m"]==20
    assert records[0]["physical_similarity_percent"] is None


def test_mro_bbox_and_site_input_validation():
    assert query_bbox(18.44,77.45,1.5).startswith("75.95,16.94")
    assert client.get("/science/mro-ctx?site_id=unknown").status_code==422
    assert client.get("/science/mro-ctx?site_id=perseverance&radius_degrees=100").status_code==422


def test_measured_evidence_has_actual_numbers_and_missing_dimensions():
    data=read_dataset()
    assert data and data["refinement"]["usable_cells"]>=8
    earth_id=data["screenings"]["mars:perseverance"][0]["id"]
    response=client.get("/science/analog-evidence",params={
        "body":"mars","site_id":"perseverance","earth_id":earth_id
    })
    assert response.status_code==200
    report=response.json()
    assert report["ready"] is True
    assert report["scientific_similarity_percent"] is None
    assert report["number_of_matched_dimensions"]==1
    assert report["total_planned_dimensions"]==8
    assert len(report["not_measured"])>=6
    record=report["measured_dimensions"][0]
    assert record["status"]=="compared_measurements"
    assert record["score"]["value"]>=0
    assert record["score"]["scientific_similarity_percent"] is None
    for metric in record["measured_comparisons"]:
        assert isinstance(metric["planetary_value"],(int,float))
        assert isinstance(metric["earth_value"],(int,float))
        assert metric["unit"]=="m"


def test_earth_candidate_not_found_no_fabricated_evidence():
    response=client.get("/science/analog-evidence",params={
        "body":"mars","site_id":"perseverance","earth_id":"not-a-record"
    })
    assert response.status_code==404
