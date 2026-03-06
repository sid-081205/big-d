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
| LSOA boundaries (2011) | `LSOA_2011_London_gen_MHW.shp` | [London Datastore](https://data.london.gov.uk/) — Statistical GIS Boundary Files for London |
| PTAL (LSOA-aggregated) | `LSOA_aggregated_PTAL_stats_2023.geojson` | [London Datastore](https://data.london.gov.uk/) — PTAL statistics aggregated to LSOA level (2021 codes) |
| Census 2021 pop density | `census2021-ts006-lsoa-populationdensity.csv` | [NOMIS](https://www.nomisweb.co.uk/) — Census 2021 TS006 (population density) by LSOA |
| Census 2021 economic activity | `census2021-ts066-lsoa-economicactivity.csv` | [NOMIS](https://www.nomisweb.co.uk/) — Census 2021 TS066 (economic activity status) by LSOA |
| Station entry/exit | `AC2023_AnnualisedEntryExit.xlsx` | [TfL Open Data](https://tfl.gov.uk/info-for/open-data-users/) — Annual station entry/exit counts |

> **Note:** The LSOA boundaries use 2011 codes (4,835 London LSOAs). PTAL and Census data use 2021 codes (4,994 LSOAs). ~96% of codes match directly; ~3.6% of LSOAs will have NaN for 2021-coded data due to boundary changes.

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
