"""Data loading functions — one per dataset, each returns GeoDataFrame/DataFrame in BNG."""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from src.config import (
    DATA_RAW, CRS_BNG, CRS_WGS84,
    STATIONS_GEOJSON, LSOA_BOUNDARIES_GPKG, PTAL_CSV,
    CENSUS_POPULATION_CSV, CENSUS_ECONOMIC_CSV,
)


def load_lsoa_boundaries() -> gpd.GeoDataFrame:
    """Load London LSOA boundary polygons (~4,835 LSOAs).

    Expects a GeoPackage or shapefile in data/raw/ containing LSOA polygons
    with at minimum an LSOA code column and geometry.
    """
    path = DATA_RAW / LSOA_BOUNDARIES_GPKG
    gdf = gpd.read_file(path)

    # Standardise LSOA code column name
    code_col = None
    for candidate in ("LSOA21CD", "LSOA11CD", "lsoa11cd", "lsoa21cd", "LSOA_CODE"):
        if candidate in gdf.columns:
            code_col = candidate
            break
    if code_col and code_col != "lsoa_code":
        gdf = gdf.rename(columns={code_col: "lsoa_code"})

    # Standardise LSOA name column
    name_col = None
    for candidate in ("LSOA21NM", "LSOA11NM", "lsoa11nm", "lsoa21nm", "LSOA_NAME"):
        if candidate in gdf.columns:
            name_col = candidate
            break
    if name_col and name_col != "lsoa_name":
        gdf = gdf.rename(columns={name_col: "lsoa_name"})

    gdf = gdf.to_crs(CRS_BNG)
    print(f"Loaded {len(gdf)} LSOA boundaries")
    return gdf


def load_station_locations() -> gpd.GeoDataFrame:
    """Load TfL station locations from downloaded GeoJSON.

    Returns GeoDataFrame with columns: id, name, modes, zone, geometry (BNG).
    """
    path = DATA_RAW / STATIONS_GEOJSON
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(CRS_BNG)
    print(f"Loaded {len(gdf)} station locations")
    return gdf


def load_ptal_grid() -> gpd.GeoDataFrame:
    """Load 100m PTAL grid as point GeoDataFrame in BNG.

    Expects CSV with columns including Easting, Northing, and an AI (Access Index)
    or PTAL score column. The PTAL grid uses BNG coordinates natively.
    """
    path = DATA_RAW / PTAL_CSV
    df = pd.read_csv(path)

    # Identify coordinate columns (case-insensitive)
    col_map = {c.lower(): c for c in df.columns}
    easting_col = col_map.get("easting") or col_map.get("x")
    northing_col = col_map.get("northing") or col_map.get("y")

    if not easting_col or not northing_col:
        raise ValueError(
            f"Cannot find Easting/Northing columns. Available: {list(df.columns)}"
        )

    geometry = [Point(x, y) for x, y in zip(df[easting_col], df[northing_col])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_BNG)

    # Standardise PTAL score column name
    for candidate in ("AI2015", "AI", "AvPTAI2015", "PTAL", "ptal"):
        if candidate in gdf.columns:
            gdf = gdf.rename(columns={candidate: "ptal_ai"})
            break

    print(f"Loaded {len(gdf)} PTAL grid points")
    return gdf


def load_imd_scores() -> pd.DataFrame:
    """Load IMD 2019 scores (Index of Multiple Deprivation).

    Returns DataFrame with LSOA code, overall IMD score, and sub-domain scores.
    """
    # Try xlsx first (gov.uk distributes as xlsx)
    xlsx_path = DATA_RAW / "imd_2019_scores.xlsx"
    csv_path = DATA_RAW / "imd_2019.csv"

    if xlsx_path.exists():
        df = pd.read_excel(xlsx_path, sheet_name=0)
    elif csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        raise FileNotFoundError(
            f"IMD data not found. Expected {xlsx_path} or {csv_path}"
        )

    # Standardise LSOA code column
    for candidate in ("LSOA code (2011)", "lsoa_code", "LSOA11CD", "FeatureCode"):
        if candidate in df.columns:
            df = df.rename(columns={candidate: "lsoa_code"})
            break

    # Standardise IMD score column
    for candidate in (
        "Index of Multiple Deprivation (IMD) Score",
        "IMD Score",
        "imd_score",
    ):
        if candidate in df.columns:
            df = df.rename(columns={candidate: "imd_score"})
            break

    print(f"Loaded IMD scores for {len(df)} LSOAs")
    return df


def load_census_population() -> pd.DataFrame:
    """Load Census 2021 population by LSOA.

    Expects CSV with LSOA code and total population columns.
    """
    path = DATA_RAW / CENSUS_POPULATION_CSV
    df = pd.read_csv(path)

    # Standardise columns
    col_map = {c.lower(): c for c in df.columns}
    for key, target in [
        ("geography code", "lsoa_code"),
        ("lsoa code", "lsoa_code"),
        ("lsoa21cd", "lsoa_code"),
        ("observation", "population"),
        ("total", "population"),
        ("all persons", "population"),
    ]:
        orig = col_map.get(key)
        if orig and orig != target:
            df = df.rename(columns={orig: target})

    print(f"Loaded Census population for {len(df)} LSOAs")
    return df


def load_census_economic_activity() -> pd.DataFrame:
    """Load Census 2021 economic activity by LSOA.

    Expects CSV with LSOA code and economic activity status columns.
    """
    path = DATA_RAW / CENSUS_ECONOMIC_CSV
    df = pd.read_csv(path)

    # Standardise LSOA code column
    col_map = {c.lower(): c for c in df.columns}
    for key in ("geography code", "lsoa code", "lsoa21cd"):
        orig = col_map.get(key)
        if orig and orig != "lsoa_code":
            df = df.rename(columns={orig: "lsoa_code"})
            break

    print(f"Loaded Census economic activity for {len(df)} LSOAs")
    return df
