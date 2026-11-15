from app.pipeline.paired_domain_scoring import score_domains, FEATURES

def measurement(value,kind,unit,source):
    return {"value":value,"unit":unit,"measurement_kind":kind,
            "spatial_support_km":24,"sampling_context":"annual_mean",
            "source_url":source}

def test_missing_domains_are_never_zero_scored():
    result=score_domains({}, {})
    assert result["overall_eight_domain_similarity_percent"] is None
    assert result["observed_domain_mean_percent"] is None
    assert result["domain_coverage_percent"]==0
    assert all(d["similarity_percent"] is None for d in result["domains"].values())

def test_matching_measured_feature_gets_100_but_not_overall():
    p={"topography":{"relief_m":measurement(200,"regional_dem_relief","m","https://pds.nasa.gov/")}}
    e={"topography":{"relief_m":measurement(200,"regional_dem_relief","m","https://earthdata.nasa.gov/")}}
    result=score_domains(p,e)
    assert result["domains"]["topography"]["similarity_percent"]==100
    assert result["domains"]["topography"]["feature_coverage_percent"]==50
    assert result["overall_eight_domain_similarity_percent"] is None

def test_incompatible_air_and_surface_temperatures_are_rejected():
    p={"temperature_illumination":{"surface_temperature_k":measurement(200,"surface_temperature","K","https://pds.nasa.gov/")}}
    e={"temperature_illumination":{"surface_temperature_k":measurement(220,"air_temperature","K","https://power.larc.nasa.gov/")}}
    result=score_domains(p,e)
    assert result["domains"]["temperature_illumination"]["features"]["surface_temperature_k"]["status"]=="incompatible_units_or_physical_quantities"

def test_all_domains_and_features_can_produce_full_index():
    p={}
    e={}
    for domain,features in FEATURES.items():
        p[domain]={}
        e[domain]={}
        for feature,spec in features.items():
            p[domain][feature]=measurement(1,spec["kind"],spec["unit"],"https://pds.nasa.gov/")
            e[domain][feature]=measurement(1,spec["kind"],spec["unit"],"https://earthdata.nasa.gov/")
    result=score_domains(p,e)
    assert result["domain_coverage_percent"]==100
    assert result["overall_eight_domain_similarity_percent"]==100
    assert result["fully_covered"]

def test_csv_import_rejects_invented_or_incompatible_measurements():
    from app.pipeline.import_paired_observations import ingest
    valid={"body":"mars","site_id":"perseverance","earth_id":"region_1",
           "side":"earth","domain":"topography","feature":"relief_m",
           "value":"200","unit":"m","measurement_kind":"regional_dem_relief",
           "spatial_support_km":"24","sampling_context":"annual_mean",
           "source_url":"https://earthdata.nasa.gov/"}
    bad={**valid,"source_url":""}
    result=ingest([valid,bad])
    assert result["import_report"]["accepted"]==1
    assert len(result["import_report"]["rejected"])==1
    assert result["earth"]["region_1"]["topography"]["relief_m"]["value"]==200
