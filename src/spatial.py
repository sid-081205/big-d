"""Stage 1 spatial computations: distance to station, PTAL averaging, master GDF."""

import numpy as np
import geopandas as gpd
import pandas as pd
from scipy.spatial import cKDTree

from src.config import DATA_PROCESSED, CRS_BNG, MASTER_GPKG, DECAY_ALPHA, CROWDING_RADIUS_M


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


def compute_lsoa_crowding_pressure(
    lsoa_gdf: gpd.GeoDataFrame,
    stations_crowding_gdf: gpd.GeoDataFrame,
    radius_m: float = CROWDING_RADIUS_M,
    decay_alpha: float = DECAY_ALPHA,
) -> pd.DataFrame:
    """Compute two crowding metrics for each LSOA centroid.

    Args:
        lsoa_gdf: LSOA polygons in BNG.
        stations_crowding_gdf: Deduplicated station points (BNG) with
            'ann_total' column (NaN for unmatched stations).
        radius_m: Search radius for crowding pressure.
        decay_alpha: Distance-decay parameter for pressure weighting.

    Returns:
        DataFrame indexed like lsoa_gdf with two columns:
            nearest_station_ann_total: ann_total at the nearest matched station.
            crowding_pressure: sum(ann_total_i * exp(-alpha * dist_i))
                               for all matched stations within radius_m.
    """
    matched = stations_crowding_gdf.dropna(subset=["ann_total"]).copy()
    if matched.empty:
        raise ValueError("No stations with crowding data found.")

    centroids = lsoa_gdf.geometry.centroid
    lsoa_coords = np.column_stack([centroids.x, centroids.y])
    station_coords = np.column_stack([matched.geometry.x, matched.geometry.y])
    ann_totals = matched["ann_total"].to_numpy()

    tree = cKDTree(station_coords)

    # Nearest matched station
    nearest_dists, nearest_idx = tree.query(lsoa_coords, k=1)
    nearest_ann = ann_totals[nearest_idx]

    # Crowding pressure: all stations within radius_m
    indices_in_radius = tree.query_ball_point(lsoa_coords, r=radius_m)
    pressure = np.array([
        np.sum(ann_totals[idx] * np.exp(-decay_alpha * np.linalg.norm(
            lsoa_coords[i] - station_coords[idx], axis=1
        ))) if len(idx) > 0 else 0.0
        for i, idx in enumerate(indices_in_radius)
    ])

    return pd.DataFrame(
        {
            "nearest_station_ann_total": nearest_ann,
            "crowding_pressure": pressure,
        },
        index=lsoa_gdf.index,
    )


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
    ptal_df: pd.DataFrame | None = None,
    imd_df: pd.DataFrame | None = None,
    census_popden_df: pd.DataFrame | None = None,
    census_econ_df: pd.DataFrame | None = None,
    crowding_df: pd.DataFrame | None = None,
    save: bool = True,
) -> gpd.GeoDataFrame:
    """Build the master LSOA GeoDataFrame by joining all Stage 1 data.

    Args:
        lsoa_gdf: LSOA boundary polygons (must have 'lsoa_code' column).
        stations_gdf: Station point locations.
        ptal_df: Pre-aggregated PTAL per LSOA (must have 'lsoa_code', 'mean_ptal_ai').
        imd_df: IMD 2019 scores (optional, must have 'lsoa_code').
        census_popden_df: Census 2021 population density (optional, must have 'lsoa_code').
        census_econ_df: Census economic activity (optional, must have 'lsoa_code').
        crowding_df: TfL annual entry/exit crowding data (optional).
        save: Whether to save the result as GeoPackage.

    Returns:
        Master GeoDataFrame with all columns joined.
    """
    master = lsoa_gdf.copy()

    # 1. Distance to nearest station
    print("Computing distance to nearest station ...")
    master["dist_to_station_m"] = compute_nearest_station_distance(master, stations_gdf)

    # 2. PTAL scores (tabular join on lsoa_code — data is pre-aggregated)
    if ptal_df is not None and "lsoa_code" in ptal_df.columns:
        print("Joining PTAL scores ...")
        ptal_cols = [c for c in ptal_df.columns if c != "lsoa_code"]
        master = master.merge(
            ptal_df[["lsoa_code"] + ptal_cols],
            on="lsoa_code",
            how="left",
        )

    # 3. IMD scores
    if imd_df is not None and "lsoa_code" in imd_df.columns:
        print("Joining IMD scores ...")
        imd_cols = [c for c in imd_df.columns if c != "lsoa_code"]
        master = master.merge(
            imd_df[["lsoa_code"] + imd_cols],
            on="lsoa_code",
            how="left",
        )

    # 4. Census 2021 population density
    if census_popden_df is not None and "lsoa_code" in census_popden_df.columns:
        print("Joining Census 2021 population density ...")
        popden_cols = [c for c in census_popden_df.columns if c != "lsoa_code"]
        master = master.merge(
            census_popden_df[["lsoa_code"] + popden_cols],
            on="lsoa_code",
            how="left",
        )

    # 5. Census economic activity
    if census_econ_df is not None and "lsoa_code" in census_econ_df.columns:
        print("Joining Census economic activity ...")
        econ_cols = [c for c in census_econ_df.columns if c != "lsoa_code"]
        master = master.merge(
            census_econ_df[["lsoa_code"] + econ_cols],
            on="lsoa_code",
            how="left",
        )

    # 6. Crowding pressure (station-level → LSOA spatial aggregation)
    if crowding_df is not None:
        print("Computing crowding pressure ...")
        from src.data_loader import join_crowding_to_stations
        stations_crowding = join_crowding_to_stations(stations_gdf, crowding_df)
        crowding_cols = compute_lsoa_crowding_pressure(master, stations_crowding)
        master["nearest_station_ann_total"] = crowding_cols["nearest_station_ann_total"]
        master["crowding_pressure"] = crowding_cols["crowding_pressure"]

    # Derived columns
    master["area_km2"] = master.geometry.area / 1e6

    # Employment rate from census economic data
    if "in_employment" in master.columns and "total_16plus" in master.columns:
        master["employment_rate"] = master["in_employment"] / master["total_16plus"]

    if save:
        out_path = DATA_PROCESSED / MASTER_GPKG
        master.to_file(out_path, driver="GPKG")
        print(f"Saved master GeoDataFrame to {out_path} ({len(master)} rows)")

    return master
