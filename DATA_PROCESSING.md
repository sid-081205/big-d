# Data Processing Pipeline

**Project:** TfL New Underground Station Analysis
**Output:** `data/processed/master_lsoa.gpkg` — 4,994 London LSOAs × 83 columns
**CRS:** EPSG:27700 (British National Grid, metres)

---

## Overview

This pipeline assembles a single spatial master dataset at Lower Layer Super Output Area (LSOA) resolution for London. Each row represents one 2021-boundary LSOA. The pipeline joins seven distinct data sources — boundaries, transport access, deprivation, census demographics, and station crowding — into one GeoPackage used for all downstream analysis.

The entry point is `notebooks/tfl_new_station_analysis.ipynb`. The source modules are:

| Module | Role |
|---|---|
| `src/config.py` | Global constants: paths, CRS, model parameters |
| `src/data_download.py` | Automated download of datasets with stable URLs |
| `src/data_loader.py` | One loader function per raw dataset; standardises column names |
| `src/spatial.py` | Spatial computations; assembles the master GeoDataFrame |

---

## Stage 1 — Raw Data Acquisition

### 1.1 Automatically Downloaded

Run `python -m src.data_download` to fetch these datasets. Each download is idempotent — it skips the file if already present.

| Dataset | File | Source | Size |
|---|---|---|---|
| TfL station locations | `tfl_stations.geojson` | TfL Unified API (`/StopPoint/Mode/tube,dlr,overground,elizabeth-line`) | ~2,640 stop points |
| IMD 2019 scores | `imd_2019.csv` | MHCLG File 7 (English Deprivation 2019) | 32,844 LSOAs (England) |
| TfL station crowding | `AC2023_AnnualisedEntryExit.xlsx` | TfL Open Data — Annual Station Counts 2023 | 430 stations |
| LSOA 2011 boundaries (fallback) | `LSOA_2011_London_gen_MHW.shp` | London Datastore GIS boundary ZIP | 4,835 LSOAs |

### 1.2 Manually Downloaded

These datasets must be saved to `data/raw/` before running the pipeline.

| Dataset | Filename | Source |
|---|---|---|
| **LSOA 2021 boundaries** | `Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BSC_V4_6453788336260919790.gpkg` | ONS Open Geography Portal — LSOA Dec 2021 EW BSC V4 |
| **PTAL LSOA-aggregated 2023** | `LSOA_aggregated_PTAL_stats_2023.geojson` | TfL GIS Open Data Hub — PTAL statistics aggregated to LSOA (2021 codes) |
| **Census 2021 — Population Density** | `census2021-ts006-lsoa-populationdensity.csv` | NOMIS — Census 2021 TS006, LSOA level bulk download |
| **Census 2021 — Economic Activity** | `census2021-ts066-lsoa-economicactivity.csv` | NOMIS — Census 2021 TS066, LSOA level bulk download |

---

## Stage 2 — Per-Dataset Loading and Standardisation

Each loader in `src/data_loader.py` returns a standardised DataFrame or GeoDataFrame. Column names are normalised to snake_case canonical names to avoid downstream join failures caused by source format variations.

### 2.1 LSOA Boundaries (`load_lsoa_boundaries`)

**Priority:** 2021 GeoPackage → 2011 shapefile fallback.

When the 2021 GeoPackage is present:

1. Load the full England & Wales GeoPackage (~35,000 LSOAs).
2. Filter to London's 4,994 LSOAs by cross-referencing the LSOA codes present in the PTAL GeoJSON (`LSOA21CD` column). This avoids maintaining a separate London boundary file.
3. Drop non-essential attribute columns (`LSOA21NMW`, `BNG_E`, `BNG_N`, `GlobalID`).
4. Rename `LSOA21CD` → `lsoa_code`, `LSOA21NM` → `lsoa_name`.
5. Reproject to EPSG:27700 (already BNG in most cases, but enforced).

**Result:** GeoDataFrame, 4,994 rows, polygon geometry in BNG.

### 2.2 Station Locations (`load_station_locations`)

The TfL API returns individual stop points (entrances, platforms). Each of the ~270 unique stations has multiple entries — typically 5–15 rows for different entrance points.

1. Load `tfl_stations.geojson` (2,640 rows).
2. Reproject to EPSG:27700.

**Result:** GeoDataFrame, 2,640 rows, point geometry. Deduplication to unique stations is performed downstream by `join_crowding_to_stations` when crowding data is joined.

### 2.3 PTAL Scores (`load_ptal_lsoa`)

Pre-aggregated PTAL access index statistics at LSOA level, computed by TfL from the 2023 PTAL grid. No spatial join is required — data already uses 2021 LSOA codes.

Column mapping from source:

| Source column | Canonical name |
|---|---|
| `LSOA21CD` | `lsoa_code` |
| `mean_AI` | `mean_ptal_ai` |
| `MEDIAN_AI` | `median_ptal_ai` |
| `MIN_AI` | `min_ptal_ai` |
| `MAX_AI` | `max_ptal_ai` |
| `MEAN_PTAL_` | `mean_ptal_level` |

**Result:** DataFrame, 4,994 rows (London LSOAs, 2021 codes).

### 2.4 IMD 2019 Scores (`load_imd_scores`)

Index of Multiple Deprivation 2019, published by MHCLG. Covers all 32,844 LSOAs in England using 2011 boundary codes.

1. Load CSV; rename `LSOA code (2011)` → `lsoa_code` and `Index of Multiple Deprivation (IMD) Score` → `imd_score`.
2. All 38 domain columns (scores, ranks, deciles for 7 deprivation domains plus sub-indices) are retained for completeness.

**Result:** DataFrame, 32,844 rows (England). After left-joining to 2021 London LSOAs, ~335 LSOAs receive NaN (6.7%) due to 2011 → 2021 LSOA boundary changes where codes do not match directly.

### 2.5 Census 2021 — Population Density (`load_census_pop_density`)

ONS Census 2021, Table TS006. Persons per square kilometre by LSOA.

Column mapping:

| Source column | Canonical name |
|---|---|
| `geography code` | `lsoa_code` |
| `Population Density: Persons per square kilometre; measures: Value` | `pop_density_2021` |

**Result:** DataFrame, 35,672 rows (England). 100% match to London 2021 LSOAs.

### 2.6 Census 2021 — Economic Activity (`load_census_economic_activity`)

ONS Census 2021, Table TS066. Economic activity status for usual residents aged 16+.

The long ONS column names are shortened:

| Canonical name | Meaning |
|---|---|
| `total_16plus` | All usual residents aged 16+ |
| `econ_active` | Economically active (excl. full-time students) |
| `in_employment` | In employment |
| `unemployed` | Unemployed |
| `econ_active_student` | Economically active full-time students |
| `econ_inactive` | Economically inactive (total) |
| `retired` | Retired |
| `student` | Inactive student |
| `looking_after_home` | Looking after home or family |
| `long_term_sick` | Long-term sick or disabled |
| `inactive_other` | Other economically inactive |

**Result:** DataFrame, 35,672 rows. 100% match to London 2021 LSOAs.

### 2.7 Station Crowding (`load_crowding_data`)

TfL Annual Station Counts 2023. The Excel file (`AC2023_AnnualisedEntryExit.xlsx`, sheet `AC23`) has a 6-row metadata header before data begins.

Processing:

1. Read with `skiprows=6`, assign 19 canonical column names manually (header row is not machine-readable).
2. Drop non-numeric rows (subtotals, blank rows) by filtering on `ann_total` parseable as numeric.
3. Retain 8 columns: `mode`, `station_name`, `ann_total`, plus day-type entry counts (`entries_mon`, `entries_mid`, `entries_fri`, `entries_sat`, `entries_sun`).

**Result:** DataFrame, 430 station-mode rows (some stations appear twice for e.g. LU + Elizabeth Line).

---

## Stage 3 — Station Name Normalisation and Crowding Join

Station crowding data uses short names (`"Acton Town"`) while the TfL GeoJSON uses fully qualified names (`"Acton Town Underground Station"`). A normalisation function strips mode/type suffixes before joining.

### `_normalise_station_name(name)`

1. Lowercase and strip whitespace.
2. Remove trailing geographic/mode suffixes in priority order: `" underground station"`, `" dlr station"`, `" overground station"`, `" elizabeth line station"`, `" rail station"`, `" tfl station"`, `" station"`.
3. Remove trailing mode abbreviations (` lu`, ` lo`, ` dlr`, ` ezl`, ` tfl`) via regex.
4. Normalise curly apostrophes to straight apostrophes.

### `join_crowding_to_stations(stations_gdf, crowding_df)`

1. Apply `_normalise_station_name` to both datasets.
2. **Deduplicate stations:** dissolve the 2,640 stop-point rows to one geometry per normalised name (~470 unique stations). The geometry is the centroid of the dissolved union, giving a single representative point per station.
3. **Aggregate crowding:** for stations served by multiple modes, sum `ann_total` across modes (e.g. Stratford: LU + Elizabeth Line + DLR combined).
4. Left-join deduplicated stations to aggregated crowding on `name_norm`.

**Match rate:** 408 / 470 stations (86.8%). Unmatched stations are mostly TfL Overground-only or national rail termini not in the GeoJSON.

---

## Stage 4 — Spatial Computations

All spatial operations use projected BNG coordinates (metres) throughout. No geographic CRS is used during computation.

### 4.1 Distance to Nearest Station (`compute_nearest_station_distance`)

Uses `scipy.spatial.cKDTree` for O(n log n) nearest-neighbour query.

- Build a KD-tree on all 2,640 station entrance coordinates.
- Query each LSOA centroid for its single nearest neighbour.
- Returns Euclidean distance in metres (straight-line, not walking distance).

**Output column:** `dist_to_station_m`

### 4.2 Crowding Pressure (`compute_lsoa_crowding_pressure`)

Computes two demand-side metrics per LSOA centroid using the deduplicated, crowding-joined station GeoDataFrame (408 matched stations).

**`nearest_station_ann_total`**
Annual entry/exit count at the nearest matched station. Provides a simple demand proxy — LSOAs near King's Cross/St. Pancras score ~72M; LSOAs near Roding Valley score ~268k.

**`crowding_pressure`**
Distance-decay weighted sum of crowding from all stations within a 960 m radius:

$$\text{crowding\_pressure}_i = \sum_{j \in N(i,\ 960\text{m})} \text{ann\_total}_j \cdot e^{-\alpha \cdot d_{ij}}$$

Where:
- $N(i, 960\text{m})$ = set of matched stations within 960 m of LSOA $i$'s centroid
- $d_{ij}$ = Euclidean distance in metres between LSOA centroid $i$ and station $j$
- $\alpha = 0.002$ (exponential decay parameter, defined in `config.py`)

`query_ball_point` from `cKDTree` retrieves all stations in radius; zero pressure is assigned for LSOAs with no stations within radius.

**Parameters** (configurable in `src/config.py`):

| Parameter | Value | Description |
|---|---|---|
| `CROWDING_RADIUS_M` | 960 | Search radius in metres |
| `DECAY_ALPHA` | 0.002 | Exponential decay coefficient |

---

## Stage 5 — Master GeoDataFrame Assembly (`build_master_geodataframe`)

All datasets are assembled via sequential left-joins on `lsoa_code`, preserving all 4,994 London 2021 LSOAs as the base. Join order:

1. LSOA boundaries (base)
2. Distance to nearest station (spatial computation)
3. PTAL scores (tabular join on `lsoa_code`)
4. IMD scores (tabular join on `lsoa_code`)
5. Census population density (tabular join on `lsoa_code`)
6. Census economic activity (tabular join on `lsoa_code`)
7. Crowding pressure (spatial computation, requires station crowding join first)

**Derived columns computed post-join:**

| Column | Formula |
|---|---|
| `area_km2` | `geometry.area / 1e6` |
| `employment_rate` | `in_employment / total_16plus` |

The assembled GeoDataFrame is saved to `data/processed/master_lsoa.gpkg` (GeoPackage, EPSG:27700).

---

## Output Schema

**File:** `data/processed/master_lsoa.gpkg`
**Rows:** 4,994 (London LSOAs, 2021 boundaries)
**Columns:** 83

### Core Identifiers

| Column | Type | Coverage | Description |
|---|---|---|---|
| `lsoa_code` | string | 100% | 2021 LSOA code (e.g. `E01000001`) |
| `lsoa_name` | string | 100% | 2021 LSOA name |
| `LAT` | float | 100% | Centroid latitude (WGS84, from GeoPackage attribute) |
| `LONG` | float | 100% | Centroid longitude (WGS84, from GeoPackage attribute) |
| `geometry` | polygon | 100% | LSOA boundary polygon, EPSG:27700 |
| `area_km2` | float | 100% | LSOA area in square kilometres |

### Transport Access

| Column | Type | Coverage | Description |
|---|---|---|---|
| `dist_to_station_m` | float | 100% | Euclidean distance (m) to nearest TfL stop point |
| `mean_ptal_ai` | float | 100% | Mean PTAL access index across LSOA (2023) |
| `median_ptal_ai` | float | 100% | Median PTAL access index |
| `min_ptal_ai` | float | 100% | Minimum PTAL access index |
| `max_ptal_ai` | float | 100% | Maximum PTAL access index |
| `mean_ptal_level` | float | 100% | Mean PTAL level (0–6b) |
| `nearest_station_ann_total` | float | 100% | Annual entry+exit count at nearest matched station (2023) |
| `crowding_pressure` | float | 100% | Distance-decay weighted crowding within 960 m (2023) |

### Deprivation (IMD 2019)

| Column | Type | Coverage | Description |
|---|---|---|---|
| `imd_score` | float | 93.3% | IMD 2019 overall score (higher = more deprived) |
| `Income Score (rate)` | float | 93.3% | Income deprivation score |
| `Employment Score (rate)` | float | 93.3% | Employment deprivation score |
| `Health Deprivation and Disability Score` | float | 93.3% | Health deprivation domain |
| `Crime Score` | float | 93.3% | Crime domain score |
| *(+ 34 further IMD rank/decile/domain columns)* | | 93.3% | All IMD 2019 sub-domain scores, ranks and deciles |

> Coverage is 93.3% (4,659/4,994) due to 2011 → 2021 LSOA boundary changes. IMD 2019 was published on 2011 geography; ~335 new or reorganised 2021 LSOAs have no direct code match.

### Demographics (Census 2021)

| Column | Type | Coverage | Description |
|---|---|---|---|
| `pop_density_2021` | float | 100% | Persons per km² (Census 2021 TS006) |
| `total_16plus` | int | 100% | All usual residents aged 16+ |
| `econ_active` | int | 100% | Economically active (excl. full-time students) |
| `in_employment` | int | 100% | In employment |
| `unemployed` | int | 100% | Unemployed |
| `econ_active_student` | int | 100% | Economically active full-time students |
| `econ_inactive` | int | 100% | Total economically inactive |
| `retired` | int | 100% | Retired |
| `student` | int | 100% | Inactive student |
| `looking_after_home` | int | 100% | Looking after home or family |
| `long_term_sick` | int | 100% | Long-term sick or disabled |
| `inactive_other` | int | 100% | Other economically inactive |
| `employment_rate` | float | 100% | `in_employment / total_16plus` |

---

## Coverage Summary

| Dataset | Matched LSOAs | Coverage |
|---|---|---|
| LSOA 2021 boundaries | 4,994 / 4,994 | 100% |
| PTAL 2023 | 4,994 / 4,994 | 100% |
| Census 2021 population density | 4,994 / 4,994 | 100% |
| Census 2021 economic activity | 4,994 / 4,994 | 100% |
| Distance to nearest station | 4,994 / 4,994 | 100% |
| Station crowding metrics | 4,994 / 4,994 | 100% |
| IMD 2019 | 4,659 / 4,994 | 93.3% |

---

## Known Limitations

**IMD geography mismatch.**
IMD 2019 uses 2011 LSOA codes. The 335 LSOAs (6.7%) with no IMD match are predominantly new LSOAs created in boundary reorganisations between 2011 and 2021. No imputation is applied; these cells remain NaN.

**Station crowding match rate.**
86.8% of unique TfL station names in the GeoJSON match to the crowding dataset. The 62 unmatched stations are mostly TfL Overground-only stations and national rail termini whose names in the GeoJSON have no corresponding entry in the AC2023 workbook. These stations contribute to `dist_to_station_m` but not to `nearest_station_ann_total` or `crowding_pressure`.

**Straight-line distances.**
`dist_to_station_m` is Euclidean (crow-flies) distance, not walking or routing distance. It systematically underestimates access time for LSOAs separated from stations by natural or man-made barriers (river, rail corridor, etc.).

**Crowding radius sensitivity.**
`crowding_pressure` is 0.0 for LSOAs with no matched station within 960 m. Approximately 25% of LSOAs fall into this category (outer London). The 960 m radius and `DECAY_ALPHA = 0.002` parameter values are configurable in `src/config.py`.

**Annual totals, not peak crowding.**
`ann_total` is the annualised total of entries and exits across all day types. It does not distinguish AM peak from off-peak, which may be more relevant to station capacity planning.
