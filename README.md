# TfL New Underground Station Analysis

Data-driven analysis to advise TfL on the optimal location for a new Underground station in London. Built for the LSESU Datathon 2026.

## Project Structure

```
aaTFL/
├── data/
│   ├── raw/            # Raw downloaded data (gitignored)
│   └── processed/      # Cleaned outputs (gitignored)
├── figures/            # Generated visualisations (gitignored)
├── notebooks/
│   └── tfl_new_station_analysis.ipynb   # Main analysis notebook
├── report/             # Final report materials
├── src/
│   ├── __init__.py
│   ├── config.py       # Constants, paths, parameters
│   ├── data_download.py # Automated dataset downloads
│   ├── data_loader.py  # Data loading functions
│   ├── spatial.py      # Spatial computations
│   └── visualisation.py # Choropleth plotting
├── .gitignore
├── README.md
└── requirements.txt
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download datasets with stable URLs
python -m src.data_download
```

## Data Acquisition

### Automatic Downloads

Running `python -m src.data_download` fetches:

| Dataset | Source | Format |
|---------|--------|--------|
| TfL station locations | TfL API | GeoJSON |
| IMD 2019 scores | gov.uk | CSV |

### Manual Downloads

The following datasets require manual download from their respective portals. Save them to `data/raw/`:

| Dataset | Filename | Source |
|---------|----------|--------|
| LSOA boundaries | `lsoa_boundaries.gpkg` | [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/) — search "LSOA Boundaries" and download the London subset as GeoPackage |
| PTAL grid | `ptal_grid.csv` | [TfL Planning](https://data.london.gov.uk/) — search "Public Transport Accessibility Levels" and download the 100m grid CSV |
| Census 2021 population | `census_2021_population.csv` | [NOMIS](https://www.nomisweb.co.uk/) — Census 2021 TS006 (population density) by LSOA |
| Census 2021 economic activity | `census_2021_economic_activity.csv` | [NOMIS](https://www.nomisweb.co.uk/) — Census 2021 TS066 (economic activity status) by LSOA |
| Station crowding | `station_crowding.xlsx` | [TfL Open Data](https://tfl.gov.uk/info-for/open-data-users/) — Annual station entry/exit counts |

## Running the Analysis

```bash
cd notebooks
jupyter notebook tfl_new_station_analysis.ipynb
```

The notebook is structured in 8 sections (Stages 1-8). Stage 1 is fully implemented; subsequent stages are outlined with placeholder headers.

## Key Design Decisions

- **CRS**: EPSG:27700 (British National Grid) for distance calculations; EPSG:4326 for Folium maps
- **Architecture**: `src/` modules imported by notebook to keep presentation clean
- **Output**: Master GeoDataFrame saved as GeoPackage (`data/processed/master_lsoa.gpkg`)
