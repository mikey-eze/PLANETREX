# PLANETREX — Official Challenge Scope and Build Contract

## Mission

Use open Earth, Moon, and Mars data from NASA and other space agencies to **discover and characterize terrestrial analog environments**, including potentially overlooked regions, relevant to future permanent lunar bases and Mars landing/exploration sites.

This is a *scientific discovery and comparison* platform, not merely a visual similarity finder, an event feed, or a static directory of famous analog sites.

## Required outcome

A person selects a documented lunar or Martian site, or a georeferenced region on the globe. PLANETREX returns candidate locations **on Earth** and shows:

1. Geographically mapped candidate locations with coordinates, region footprint, and dataset spatial resolution.
2. Side-by-side actual observed/model-derived values, units, measurement dates, coverage and citations for the selected planetary region and the terrestrial region.
3. A similarity or suitability *screening* result for each comparable feature, with explicit explanation of non-comparable and missing features.
4. Score provenance: feature transformations, weight choices, uncertainty, missingness, and a clear statement of whether the metric is validated. Never present a manually curated tag-overlap percentage as scientific physical similarity.
5. What the Earth analogue can be used for (e.g. mobility testing, drilling, instrumentation, science operations) and where the analogy fails (gravity, vacuum/atmosphere, radiation, etc.).
6. A discovery explanation: *why this previously overlooked site appears*, not merely a familiar-site recommendation.

## Scientific dimensions (modular, evidence gated)

- Geology, mineralogy, regolith and surface materials
- Terrain, slope, elevation, roughness, cratering
- Temperature, solar illumination, environmental extremes
- Water, ice, permafrost and potential resources
- Aeolian processes, dust, wind, erosion and sedimentation
- Biology, habitability, biosignatures (when appropriate to Earth; not implying life on Mars)
- Caves, lava tubes and subsurface structures
- Operations: access, mobility, robotic navigation, drilling and engineering constraints

A location may be strong in one dimension and weak in another. No global one-number score is valid unless assumptions and coverage are explicit.

## Source catalogue / ingestion candidates

| Body | Priority sources | Variables | State |
|---|---|---|---|
| Earth | NASA Earthdata (DAAC catalog and scientific products) | terrain, geology-adjacent land observations, thermal, water, aerosols | **Not yet ingested for analog comparison** |
| Earth | Copernicus DEM GLO-90 (through Open-Meteo point elevation) | Earth elevation | Sampler code exists; no deployed worldwide scientific pipeline |
| Earth | ESA Copernicus Data Space Sentinel products | multispectral, land surface, SAR | Proposed; not integrated |
| Earth | CSA RADARSAT open data | radar/backscatter, ice, surface characteristics | Proposed; not integrated |
| Earth | JAXA G-Portal | Earth observation, snow, vegetation etc. | Proposed; not integrated |
| Moon | NASA PDS / LRO LOLA | elevation, slope, geomorphology | Proposed measurement ingestion |
| Moon | NASA LRO Diviner | surface temperature and polar environments | Proposed measurement ingestion |
| Moon | NASA LRO LROC, Mini-RF, LEND | imaging, radar, hydrogen proxies | Proposed measurement ingestion |
| Mars | NASA PDS / MRO instruments | terrain, imagery, mineralogy, atmosphere | Proposed measurement ingestion |
| Mars | NASA mission records | landing site coordinates, mission context | Navigation reference only today |
| All | NASA PDS Search | planetary archive discovery metadata | Integrated endpoint; relevance must be validated |
| All | NASA Image & Video Library | archive imagery and captions | Integrated endpoint; not a scientific feature raster |
| Earth | NASA EONET | natural-event information | Integrated live panel; not a validated analog-comparison dataset |

Source onboarding requires verification of licenses, coordinate conventions, resolution, physical units, spatial footprint and temporal relevance. Discovery/search endpoints are **not** automatically scientific measurements.

## Scientific pipeline: data first, not recalculation on page load

1. **Catalog:** record source URLs, mission/instrument, version, licenses, spatial/temporal coverage, CRS, units and retrieval date.
2. **Ingest:** perform reviewed one-time or batch downloads of official measured products. Version and checksum the source files.
3. **Normalize:** harmonize feature units, rasters/regions, planetary coordinate frames, area and resolution without introducing fake precision.
4. **Screen Earth globally:** use coarse-to-fine geographic tiling and multiple environment classes (desert, polar, volcanic, arid, impact, cave, salt flat, glacier, etc.). Avoid ocean-only candidates where land suitability is required.
5. **Derive comparable features:** use appropriate statistics/footprints and record uncertainty; do not equate point elevation with region-scale topographic morphology.
6. **Rank cautiously:** per-feature distances/coverage, confidence and transparent weights; avoid fabricated 90%+ "matches". Exclude unavailable dimensions and identify them explicitly.
7. **Persist:** searchable region profiles, candidate pairs, rankings, source provenance and method version in a persistent production data store.
8. **Serve:** a fast read API for the interactive Moon/Mars → Earth workflow. Keep API live-data cards separate from scientific comparison results.
9. **Validate:** scientific sanity tests, independent documented analog case studies and unexpected-site checks; do not label a new discovery as validated without supporting measurements.

## Website behavior

- Moon-first, Mars toggle, meaningful planetary textures and readable geographic markers.
- Clicking a *known* site reveals measured reference information; selecting an arbitrary region is supported **only** when source data covers it. Otherwise return an honest “data unavailable” status.
- Clicking a planetary region shows an Earth globe/map with **measured and ranked** analog candidates, not unassessed grid cells.
- Each candidate has a compact evidence panel, units, overlap/mismatch explanation, source URLs, confidence/data coverage and use-case relevance.
- Distinguish **live events / image archive / scientific datasets / computed analog candidates** visually and conceptually.
- Responsive viewport, accessible controls and functional page scrolling.

## Current prototype status (do not misrepresent)

- FastAPI on Render and GitHub auto-deploy; Moon/Mars site navigation.
- NASA EONET events and Image Library search; PDS metadata discovery.
- Local scientific profile/terrain comparison scaffolding and simple geography grid.
- Hard-coded Earth example locations with descriptive tags. The displayed percentage is a **Jaccard tag-overlap** percentage, **not a quantitative scientific similarity score**.
- No validated global scan, no populated production measurement corpus, no full LRO/MRO/Earthdata multidimensional comparison yet.
- No claim that the site is production-ready for permanent-base selection.

## First milestone: defensible mini-pilot

For a selected Apollo/LRO and a selected Mars/MRO region:
- Verify one real lunar feature dataset, one real Mars feature dataset, and a genuinely comparable measured Earth feature dataset.
- Process a small but *systematically sampled* set of Earth regions (not merely selected famous analogs).
- Save each real measurement with source citation/units/coverage.
- Produce reproducible and explicitly unvalidated feature-distance rankings with identified mismatch factors.
- Have a browser action fetch the stored rankings and map the result.
- Add automated tests for source target body, units, missingness, coverage, and nonfabrication.

### Success criterion

A judge can select Moon or Mars, inspect actual Earth candidates and demonstrate **which measured dimensions match, which do not, where data comes from, and how this helps exploration**. The system must not pass off tags, textures, catalogue titles, or event locations as scientific measurements.
