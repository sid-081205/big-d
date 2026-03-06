"""Stage 1 spatial computations: distance to station, PTAL averaging, master GDF."""

import numpy as np
import geopandas as gpd
import pandas as pd
from scipy.spatial import cKDTree

from src.config import DATA_PROCESSED, CRS_BNG, MASTER_GPKG


def compute_nearest_station_distance(
    lsoa_gdf: gpd.GeoDataFrame,
    stations_gdf: gpd.GeoDataFrame,
) -> pd.Series:
    """Compute distance (m) from each LSOA centroid to nearest station.

    Uses scipy cKDTree for O(n log n) performance.
    Both inputs must be in the same projected CRS (BNG).

    Returns:
        pd.Series indexed like lsoa_gdf with distances in metres.
    """
    centroids = lsoa_gdf.geometry.centroid
    lsoa_coords = np.column_stack([centroids.x, centroids.y])
    station_coords = np.column_stack([
        stations_gdf.geometry.x, stations_gdf.geometry.y
    ])

    tree = cKDTree(station_coords)
    distances, _ = tree.query(lsoa_coords, k=1)

    return pd.Series(distances, index=lsoa_gdf.index, name="dist_to_station_m")


def spatial_average_ptal(
    lsoa_gdf: gpd.GeoDataFrame,
    ptal_gdf: gpd.GeoDataFrame,
) -> pd.Series:
    """Compute mean PTAL access index per LSOA via spatial join.

    Joins PTAL grid point centroids to LSOA polygons and computes the
    mean of the 'ptal_ai' column for each LSOA.

    Returns:
        pd.Series indexed like lsoa_gdf with mean PTAL AI scores.
    """
    # Ensure both are in BNG
    if lsoa_gdf.crs != CRS_BNG:
        lsoa_gdf = lsoa_gdf.to_crs(CRS_BNG)
    if ptal_gdf.crs != CRS_BNG:
        ptal_gdf = ptal_gdf.to_crs(CRS_BNG)

    # Spatial join: assign each PTAL point to an LSOA
    joined = gpd.sjoin(
        ptal_gdf[["ptal_ai", "geometry"]],
        lsoa_gdf[["geometry"]],
        how="inner",
        predicate="within",
    )

    # Group by LSOA index and take mean
    mean_ptal = joined.groupby("index_right")["ptal_ai"].mean()
    mean_ptal.index.name = None
    mean_ptal.name = "mean_ptal_ai"

    # Reindex to match lsoa_gdf (NaN for LSOAs with no PTAL points)
    return mean_ptal.reindex(lsoa_gdf.index)


def build_master_geodataframe(
    lsoa_gdf: gpd.GeoDataFrame,
    stations_gdf: gpd.GeoDataFrame,
    ptal_gdf: gpd.GeoDataFrame | None = None,
    imd_df: pd.DataFrame | None = None,
    census_pop_df: pd.DataFrame | None = None,
    census_econ_df: pd.DataFrame | None = None,
    save: bool = True,
) -> gpd.GeoDataFrame:
    """Build the master LSOA GeoDataFrame by joining all Stage 1 data.

    Args:
        lsoa_gdf: LSOA boundary polygons (must have 'lsoa_code' column).
        stations_gdf: Station point locations.
        ptal_gdf: PTAL grid points (optional).
        imd_df: IMD 2019 scores (optional, must have 'lsoa_code').
        census_pop_df: Census population (optional, must have 'lsoa_code').
        census_econ_df: Census economic activity (optional, must have 'lsoa_code').
        save: Whether to save the result as GeoPackage.

    Returns:
        Master GeoDataFrame with all columns joined.
    """
    master = lsoa_gdf.copy()

    # 1. Distance to nearest station
    print("Computing distance to nearest station ...")
    master["dist_to_station_m"] = compute_nearest_station_distance(master, stations_gdf)

    # 2. PTAL scores
    if ptal_gdf is not None:
        print("Computing spatial average PTAL ...")
        master["mean_ptal_ai"] = spatial_average_ptal(master, ptal_gdf)

    # 3. IMD scores
    if imd_df is not None and "lsoa_code" in imd_df.columns:
        print("Joining IMD scores ...")
        imd_cols = [c for c in imd_df.columns if c != "lsoa_code"]
        master = master.merge(
            imd_df[["lsoa_code"] + imd_cols],
            on="lsoa_code",
            how="left",
        )

    # 4. Census population
    if census_pop_df is not None and "lsoa_code" in census_pop_df.columns:
        print("Joining Census population ...")
        pop_cols = [c for c in census_pop_df.columns if c not in ("lsoa_code",)]
        master = master.merge(
            census_pop_df[["lsoa_code"] + pop_cols],
            on="lsoa_code",
            how="left",
        )

    # 5. Census economic activity
    if census_econ_df is not None and "lsoa_code" in census_econ_df.columns:
        print("Joining Census economic activity ...")
        econ_cols = [c for c in census_econ_df.columns if c not in ("lsoa_code",)]
        master = master.merge(
            census_econ_df[["lsoa_code"] + econ_cols],
            on="lsoa_code",
            how="left",
        )

    # Compute area and population density if population available
    master["area_km2"] = master.geometry.area / 1e6
    if "population" in master.columns:
        master["pop_density_km2"] = master["population"] / master["area_km2"]

    if save:
        out_path = DATA_PROCESSED / MASTER_GPKG
        master.to_file(out_path, driver="GPKG")
        print(f"Saved master GeoDataFrame to {out_path} ({len(master)} rows)")

    return master
