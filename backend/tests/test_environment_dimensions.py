"""Regression checks for real temperature, hydrology and MRO raster provenance.

Pure parsing tests never contact NASA, and reject missing/poor-quality data
rather than fabricating physical similarity percentages.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.earth_surface import subset_group,temperature_summary
from app.api.routes.earth_processes import summarize_power
from app.api.routes.mro_measured import read_mro

client=TestClient(app)


def test_modis_temperature_uses_qc_and_scaling():
    data={"ncols":1,"nrows":1,"subset":[
        {"modis_date":"A2025001","band":"LST_Day_1km","data":[15000]},
        {"modis_date":"A2025001","band":"QC_Day","data":[0]},
        {"modis_date":"A2025009","band":"LST_Day_1km","data":[15000]},
        {"modis_date":"A2025009","band":"QC_Day","data":[1]},
        {"modis_date":"A2025017","band":"LST_Day_1km","data":[0]},
        {"modis_date":"A2025017","band":"QC_Day","data":[0]},
    ]}
    row=temperature_summary(data,"LST_Day_1km","QC_Day")
    assert row["accepted_composites"]==1
    assert row["rejected_or_missing_composites"]==2
    assert row["value"]==26.85
    assert row["total_composites"]==3
    assert row["unit"]=="°C"


def test_modis_missing_qc_not_treated_as_valid_temperature():
    data={"ncols":1,"nrows":1,"subset":[
        {"modis_date":"A2025001","band":"LST_Night_1km","data":[16000]}
    ]}
    row=temperature_summary(data,"LST_Night_1km","QC_Night")
    assert row["value"] is None
    assert row["accepted_composites"]==0


def test_power_process_units_and_sentinels():
    data={"parameters":{"ALLSKY_SFC_SW_DWN":{"units":"MJ/m^2/day"}},
          "properties":{"parameter":{
      "T2M":{"d1":14,"d2":16,"d3":-999},
      "PRECTOTCORR":{"d1":1.3,"d2":2.4},
      "WS10M":{"d1":4,"d2":5},
      "ALLSKY_SFC_SW_DWN":{"d1":5.5,"d2":6.5}
    }}}
    result=summarize_power(data)
    assert result["T2M"]["value"]==15.0
    assert result["PRECTOTCORR"]["value"]==3.7
    assert result["WS10M"]["value"]==4.5
    assert result["ALLSKY_SFC_SW_DWN"]["value"]==1.667  # 6 MJ/m²/day -> kWh/m²/day
    assert result["T2M"]["sample_days"]==2

def test_real_mro_rasters_are_independent_of_analog_score():
    payload=read_mro()
    assert payload is not None
    assert payload["used_in_analog_scoring"] is False
    assert payload["measured_dtm_count"]>=1
    r=client.get("/science/mro-ctx-measured?site_id=perseverance")
    assert r.status_code==200
    data=r.json()
    assert data["count"]>=1
    assert data["used_in_analog_scoring"] is False
    assert data["scientific_similarity_percent"] is None
    assert all(x["measurement"]["valid_pixel_fraction"]>=0.15 for x in data["scenes"])
    assert all(x["asset_url"].startswith("https://") for x in data["scenes"])


def test_coverage_never_marks_unprocessed_dimensions_as_validated():
    r=client.get("/science/coverage")
    assert r.status_code==200
    d=r.json()
    assert d["total_planned_dimensions"]==8
    assert d["measured_comparable_dimensions"]==1
    assert d["scientific_similarity_percent"] is None
    assert d["validated_full_multidimensional_analog_discoveries"]==0
    assert len([x for x in d["dimensions"] if
                x["paired_measurement_status"]=="preliminary_measured_two_metric_screening"])==1


def test_environment_endpoints_reject_invalid_coordinates():
    for endpoint in ("earth-processes","earth-surface"):
        r=client.get(f"/science/{endpoint}?latitude=91&longitude=10")
        assert r.status_code==422
