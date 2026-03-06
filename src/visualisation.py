"""Stage 1 choropleth visualisations."""

import matplotlib.pyplot as plt
import geopandas as gpd

from src.config import FIGURES_DIR, CRS_BNG


def _base_choropleth(
    gdf: gpd.GeoDataFrame,
    column: str,
    title: str,
    cmap: str,
    legend_label: str,
    filename: str,
    figsize: tuple = (12, 14),
) -> plt.Figure:
    """Create and save a choropleth map."""
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    gdf.plot(
        column=column,
        cmap=cmap,
        legend=True,
        legend_kwds={"label": legend_label, "shrink": 0.6},
        ax=ax,
        edgecolor="face",
        linewidth=0.2,
    )
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_axis_off()
    fig.tight_layout()

    out_path = FIGURES_DIR / filename
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Saved {out_path}")
    return fig


def plot_distance_to_station(gdf: gpd.GeoDataFrame) -> plt.Figure:
    """V1: Distance to nearest station choropleth (YlOrRd)."""
    return _base_choropleth(
        gdf=gdf,
        column="dist_to_station_m",
        title="Distance to Nearest Underground/Rail Station",
        cmap="YlOrRd",
        legend_label="Distance (metres)",
        filename="v1_distance_to_station.png",
    )


def plot_ptal_scores(gdf: gpd.GeoDataFrame) -> plt.Figure:
    """V2: Mean PTAL access index choropleth (RdYlGn)."""
    return _base_choropleth(
        gdf=gdf,
        column="mean_ptal_ai",
        title="Public Transport Accessibility Level (PTAL)",
        cmap="RdYlGn",
        legend_label="Mean PTAL Access Index",
        filename="v2_ptal_scores.png",
    )


def plot_population_density(gdf: gpd.GeoDataFrame) -> plt.Figure:
    """V3: Population density choropleth (Blues)."""
    return _base_choropleth(
        gdf=gdf,
        column="pop_density_km2",
        title="Population Density by LSOA",
        cmap="Blues",
        legend_label="Population per km²",
        filename="v3_population_density.png",
    )
