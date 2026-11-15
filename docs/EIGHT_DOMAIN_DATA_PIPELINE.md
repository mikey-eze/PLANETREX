# PLANETREX: eight-domain evidence ingestion

This is a build specification, not a claim that all eight domains have been measured.

## Data sources to process
- **Geology/mineralogy:** Moon LRO Diviner spectral products and Apollo laboratory samples; Mars MRO CRISM / TES / rover chemistry; Earth geological maps and matched spectral/chemical surveys. A mapped lithology name is not a mineral abundance.
- **Topography:** NASA LOLA (Moon), MOLA (Mars), ASTER DEM (Earth). Existing regional relief and height variation are measured; harmonize resolution and footprints before strong claims.
- **Temperature/illumination:** Moon Diviner gridded surface temperature, Mars THEMIS/TES thermal products, Earth MODIS land-surface temperature. Match local solar time, season and sampling context. NASA POWER 2-m air temperature is NOT surface temperature.
- **Water/ice:** LRO LEND/LAMP, Mars Odyssey neutron / CRISM hydration, Earth satellite snow/ice and field water-content products. Ice presence and liquid water are distinct observables.
- **Dust/wind:** Mars atmospheric winds and surface particle-size distributions; Earth weather/reanalysis and sediment surveys. Lunar vacuum has no wind, so wind is not a meaningful lunar match.
- **Biology/habitability:** Earth organic carbon, vegetation and geochemical context; planetary organic chemistry and environmental habitability constraints where measured. Do not imply extraterrestrial biology has been observed.
- **Caves/subsurface:** Lunar and Martian radar/lava-tube candidates, Earth subsurface geophysics. A remotely inferred void and a ground-verified cave are different evidence classes.
- **Engineering/resources:** DEM slope/roughness, rover surface rock abundance and measured geotechnical properties. Never substitute an orbital image for bearing-strength tests.

NASA planetary archives: https://pds.nasa.gov/ and https://ode.rsl.wustl.edu/
LRO Diviner archive: https://pds-geosciences.wustl.edu/missions/lro/diviner.htm
Earth MODIS: https://modis.ornl.gov/data/modis_webservice.html
NASA POWER: https://power.larc.nasa.gov/

## Processing contract
1. Download actual measurement products with metadata and QA masks.
2. Extract numeric values for planetary and Earth footprints; record product/version, coordinate reference, resolution, observation time, and quality filters.
3. Convert physical units, harmonize spatial support and observation context.
4. Export verified observations as CSV with the fields specified in `app.pipeline.import_paired_observations`.
5. Run `python -m app.pipeline.import_paired_observations --input measurements.csv`.
6. Run `python -m app.pipeline.build_analog_catalog`.
7. The Data section displays each domain's measured index and feature coverage. Missing data is explicitly marked unavailable.

## Scoring contract
`paired_domain_scoring.py` defines the feature registry and fixed comparison scales. Scores are **descriptive indices**, not probabilities or validated analog-certification percentages. The overall eight-domain index is only returned if every registered feature has a compatible measured pair. An observed-domain mean is never labeled as the complete score.

## Current blockers
This repository does not yet contain harmonized planetary and Earth measurements for every registered feature. No implementation should manufacture values or claim complete eight-domain results until the source processing is actually performed and validated.
