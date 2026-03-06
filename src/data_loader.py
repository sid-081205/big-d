"""Data loading functions — one per dataset, each returns GeoDataFrame/DataFrame in BNG.

Each loader is tolerant of the file variants that data_download.py may produce
(CSV vs XLSX, shapefile vs GeoPackage, etc.) and standardises column names to
the canonical names used downstream:

    lsoa_code, lsoa_name, imd_score, mean_ptal_ai, population, ...
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point

from src.config import (
    DATA_RAW, CRS_BNG, CRS_WGS84,
    STATIONS_GEOJSON, LSOA_BOUNDARIES_GPKG, PTAL_CSV, PTAL_LSOA_GEOJSON,
    IMD_CSV, CENSUS_POPDEN_CSV, CENSUS_ECONOMIC_CSV,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _find_and_rename(
    df: pd.DataFrame | gpd.GeoDataFrame,
    candidates: list[str],
    target: str,
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Rename the first matching column from *candidates* to *target*."""
    if target in df.columns:
        return df
    for c in candidates:
        if c in df.columns:
            return df.rename(columns={c: target})
    return df


def _resolve_path(primary: Path, *fallbacks: Path) -> Path:
    """Return the first path that exists, or raise FileNotFoundError."""
    for p in (primary, *fallbacks):
        if p.exists():
            return p
    tried = ", ".join(str(p) for p in (primary, *fallbacks))
    raise FileNotFoundError(f"None of these files exist: {tried}")


# ── 1. LSOA boundaries ─────────────────────────────────────────────────────

def load_lsoa_boundaries() -> gpd.GeoDataFrame:
    """Load London LSOA boundary polygons (~4,835 LSOAs).

    Tries (in order):
      1. The GeoPackage path from config  (LSOA_BOUNDARIES_GPKG)
      2. Extracted shapefile from data_download.py  (LSOA_2011_London_gen_MHW.shp)
      3. Subdirectory from the London Datastore ZIP
    """
    candidates = [
        DATA_RAW / LSOA_BOUNDARIES_GPKG,
        DATA_RAW / "LSOA_2011_London_gen_MHW.shp",
        DATA_RAW / "statistical-gis-boundaries-london" / "ESRI"
        / "LSOA_2011_London_gen_MHW.shp",
    ]
    path = _resolve_path(*candidates)
    gdf = gpd.read_file(path)

    # Standardise LSOA code column
    gdf = _find_and_rename(
        gdf,
        ["LSOA21CD", "LSOA11CD", "lsoa11cd", "lsoa21cd", "LSOA_CODE"],
        "lsoa_code",
    )
    # Standardise LSOA name column
    gdf = _find_and_rename(
        gdf,
        ["LSOA21NM", "LSOA11NM", "lsoa11nm", "lsoa21nm", "LSOA_NAME"],
        "lsoa_name",
    )

    gdf = gdf.to_crs(CRS_BNG)
    print(f"Loaded {len(gdf)} LSOA boundaries from {path.name}")
    return gdf


# ── 2. Station locations ───────────────────────────────────────────────────

def load_station_locations() -> gpd.GeoDataFrame:
    """Load TfL station locations from downloaded GeoJSON.

    Returns GeoDataFrame with columns: id, name, modes, zone, geometry (BNG).
    """
    path = DATA_RAW / STATIONS_GEOJSON
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(CRS_BNG)
    print(f"Loaded {len(gdf)} station locations")
    return gdf


# ── 3. PTAL (LSOA-aggregated) ─────────────────────────────────────────────

def load_ptal_lsoa() -> pd.DataFrame:
    """Load pre-aggregated PTAL statistics per LSOA (2021 codes).

    Reads LSOA_aggregated_PTAL_stats_2023.geojson, extracts tabular columns
    (no geometry needed since we join by LSOA code).

    Returns DataFrame with: lsoa_code, mean_ptal_ai, median_ptal_ai,
    min_ptal_ai, max_ptal_ai, mean_ptal_level.
    """
    path = DATA_RAW / PTAL_LSOA_GEOJSON
    gdf = gpd.read_file(path)

    df = pd.DataFrame({
        "lsoa_code": gdf["LSOA21CD"],
        "mean_ptal_ai": gdf["mean_AI"],
        "median_ptal_ai": gdf["MEDIAN_AI"],
        "min_ptal_ai": gdf["MIN_AI"],
        "max_ptal_ai": gdf["MAX_AI"],
        "mean_ptal_level": gdf["MEAN_PTAL_"],
    })

    print(f"Loaded PTAL stats for {len(df)} LSOAs")
    return df


def load_ptal_grid() -> gpd.GeoDataFrame:
    """Load 100m PTAL grid as point GeoDataFrame in BNG (legacy fallback).

    Expects CSV with columns including Easting/X, Northing/Y, and an
    access index (AI) or PTAL score column.
    """
    path = DATA_RAW / PTAL_CSV
    df = pd.read_csv(path)

    col_map = {c.lower(): c for c in df.columns}
    easting_col = col_map.get("easting") or col_map.get("x")
    northing_col = col_map.get("northing") or col_map.get("y")

    if not easting_col or not northing_col:
        raise ValueError(
            f"Cannot find Easting/Northing columns. Available: {list(df.columns)}"
        )

    geometry = [Point(x, y) for x, y in zip(df[easting_col], df[northing_col])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_BNG)

    gdf = _find_and_rename(
        gdf,
        ["AI2015", "AI2023", "AI", "AvPTAI2015", "AvPTAI2023", "PTAL", "ptal"],
        "ptal_ai",
    )

    print(f"Loaded {len(gdf)} PTAL grid points")
    return gdf


# ── 4. IMD 2019 scores ─────────────────────────────────────────────────────

def load_imd_scores() -> pd.DataFrame:
    """Load IMD 2019 scores (Index of Multiple Deprivation).

    Returns DataFrame with lsoa_code, imd_score, and all domain columns.
    """
    csv_path = DATA_RAW / IMD_CSV
    xlsx_path = DATA_RAW / "imd_2019_scores.xlsx"

    if csv_path.exists():
        df = pd.read_csv(csv_path)
    elif xlsx_path.exists():
        df = pd.read_excel(xlsx_path, sheet_name=0)
    else:
        raise FileNotFoundError(
            f"IMD data not found. Expected {csv_path} or {xlsx_path}. "
            f"Run `python -m src.data_download` first."
        )

    df = _find_and_rename(
        df,
        ["LSOA code (2011)", "LSOA11CD", "lsoa_code", "FeatureCode"],
        "lsoa_code",
    )
    df = _find_and_rename(
        df,
        [
            "Index of Multiple Deprivation (IMD) Score",
            "IMD Score",
            "imd_score",
        ],
        "imd_score",
    )

    print(f"Loaded IMD scores for {len(df)} LSOAs")
    return df


# ── 5. Census 2021 population density ────────────────────────────────────

def load_census_pop_density() -> pd.DataFrame:
    """Load Census 2021 population density (TS006) by LSOA.

    Returns DataFrame with lsoa_code and pop_density_2021 columns.
    """
    path = DATA_RAW / CENSUS_POPDEN_CSV
    df = pd.read_csv(path)

    df = df.rename(columns={
        "geography code": "lsoa_code",
        "Population Density: Persons per square kilometre; measures: Value": "pop_density_2021",
    })
    df = df[["lsoa_code", "pop_density_2021"]]

    print(f"Loaded Census population density for {len(df)} LSOAs")
    return df


# ── 6. Census 2021 economic activity ─────────────────────────────────────

def load_census_economic_activity() -> pd.DataFrame:
    """Load Census 2021 economic activity (TS066) by LSOA.

    Shortens the very long ONS column names to usable keys.
    Returns DataFrame with lsoa_code and summary economic columns.
    """
    path = DATA_RAW / CENSUS_ECONOMIC_CSV
    df = pd.read_csv(path)

    # Build rename map for the long column names
    rename_map = {
        "geography code": "lsoa_code",
        "Economic activity status: Total: All usual residents aged 16 years and over": "total_16plus",
        "Economic activity status: Economically active (excluding full-time students)": "econ_active",
        "Economic activity status: Economically active (excluding full-time students):In employment": "in_employment",
        "Economic activity status: Economically active (excluding full-time students): Unemployed": "unemployed",
        "Economic activity status: Economically active and a full-time student": "econ_active_student",
        "Economic activity status: Economically inactive": "econ_inactive",
        "Economic activity status: Economically inactive: Retired": "retired",
        "Economic activity status: Economically inactive: Student": "student",
        "Economic activity status: Economically inactive: Looking after home or family": "looking_after_home",
        "Economic activity status: Economically inactive: Long-term sick or disabled": "long_term_sick",
        "Economic activity status: Economically inactive: Other": "inactive_other",
    }

    df = df.rename(columns=rename_map)

    # Keep only the renamed summary columns
    keep_cols = ["lsoa_code"] + [v for v in rename_map.values() if v != "lsoa_code"]
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols]

    print(f"Loaded Census economic activity for {len(df)} LSOAs")
    return df


# ── 7. Crowding data (station entry/exit) ──────────────────────────────────

def load_crowding_data() -> pd.DataFrame:
    """Load TfL annual station entry/exit counts."""
    candidates = [
        DATA_RAW / "AC2023_AnnualisedEntryExit.xlsx",
        DATA_RAW / "AC2024_AnnualisedEntryExit_CrowdingPublic.xlsm",
    ]
    for p in sorted(DATA_RAW.glob("AC*_Annualised*.xls*")):
        if p not in candidates:
            candidates.append(p)

    path = _resolve_path(*candidates)

    df = pd.read_excel(path, sheet_name=0)
    print(f"Loaded crowding data from {path.name} ({len(df)} rows)")
    return df
