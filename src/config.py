"""Project-wide constants and paths."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
FIGURES_DIR = PROJECT_ROOT / "figures"

# Ensure directories exist
for _d in (DATA_RAW, DATA_PROCESSED, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Coordinate Reference Systems ───────────────────────────────────────
CRS_BNG = "EPSG:27700"     # British National Grid (metres)
CRS_WGS84 = "EPSG:4326"   # WGS-84 (lat/lon)

# ── Model Parameters ──────────────────────────────────────────────────
CATCHMENT_RADIUS_M = 800       # Walking catchment around stations (m)
DECAY_ALPHA = 0.002            # Exponential distance-decay parameter
TRANSFER_PENALTY_MIN = 3       # Transfer penalty (minutes)

# ── Expected Data Filenames (in data/raw/) ─────────────────────────────
STATIONS_GEOJSON = "tfl_stations.geojson"
IMD_CSV = "imd_2019.csv"
CROWDING_XLSX = "station_crowding.xlsx"
LSOA_BOUNDARIES_GPKG = "lsoa_boundaries.gpkg"
PTAL_CSV = "ptal_grid.csv"                          # legacy 100m grid
PTAL_LSOA_GEOJSON = "LSOA_aggregated_PTAL_stats_2023.geojson"
CENSUS_POPDEN_CSV = "census2021-ts006-lsoa-populationdensity.csv"
CENSUS_ECONOMIC_CSV = "census2021-ts066-lsoa-economicactivity.csv"

# ── Output Filenames (in data/processed/) ──────────────────────────────
MASTER_GPKG = "master_lsoa.gpkg"
