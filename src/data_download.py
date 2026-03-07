"""Automated downloads for datasets with stable URLs.

Run directly:  python -m src.data_download

URL verification log (March 2026):
  - IMD File 7 CSV:  ✅ 200 text/csv   (assets.publishing.service.gov.uk)
  - TfL StopPoint:   ✅ 200 JSON       (api.tfl.gov.uk, paginated)
  - Crowding 2023:   ✅ 200 xlsx        (crowding.data.tfl.gov.uk)
  - LSOA boundaries: ✅ 200 zip         (data.london.gov.uk)
"""

import json
import zipfile
import io
import requests
from pathlib import Path

from src.config import DATA_RAW, STATIONS_GEOJSON, IMD_CSV


# ---------------------------------------------------------------------------
# TfL Crowding: data is organised by year under
#   https://crowding.data.tfl.gov.uk/Annual%20Station%20Counts/{year}/
#
# Verified working as of March 2026:
#   2023 → AC2023_AnnualisedEntryExit.xlsx   ✅ HTTP 200
#   2024 → .xlsm file was indexed but now 404s; use 2023 as stable latest.
# ---------------------------------------------------------------------------
_CROWDING_YEAR = "2023"
_CROWDING_FILENAME = f"AC{_CROWDING_YEAR}_AnnualisedEntryExit.xlsx"
CROWDING_XLSX = _CROWDING_FILENAME

# LSOA boundary zip internal path
_LSOA_SHP_SUBPATH = (
    "statistical-gis-boundaries-london/ESRI/LSOA_2011_London_gen_MHW.shp"
)


def _download_file(url: str, dest: Path, description: str) -> Path:
    """Download a file if it doesn't already exist."""
    if dest.exists():
        print(f"  [skip] {description} already exists: {dest.name}")
        return dest
    print(f"  [download] {description} ...")
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  [done] Saved {dest.name} ({len(resp.content) / 1_048_576:.1f} MB)")
    return dest


# ── 1. TfL station locations ───────────────────────────────────────────────

def download_station_locations() -> Path:
    """Download TfL station locations from the Unified API StopPoint endpoint.

    The /StopPoint/Mode/{modes} endpoint returns paginated JSON when the
    result set is large.  We iterate through all pages and merge them into
    a single GeoJSON FeatureCollection.

    Verified: api.tfl.gov.uk is live (March 2026).  Works without app_key
    at reduced rate limits; register at https://api-portal.tfl.gov.uk/ for
    500 req/min.
    """
    dest = DATA_RAW / STATIONS_GEOJSON
    if dest.exists():
        print(f"  [skip] Station locations already exist: {dest.name}")
        return dest

    print("  [download] TfL station locations (Unified API, paginated) ...")

    base_url = (
        "https://api.tfl.gov.uk/StopPoint/Mode/tube,dlr,overground,elizabeth-line"
    )
    page = 1
    all_stops: list[dict] = []

    while True:
        resp = requests.get(
            base_url,
            params={"page": page},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        stops = data.get("stopPoints", [])
        if not stops:
            break
        all_stops.extend(stops)

        total = data.get("total", 0)
        if total and len(all_stops) >= total:
            break
        page += 1

    # Convert to GeoJSON FeatureCollection
    features = []
    for stop in all_stops:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [stop["lon"], stop["lat"]],
            },
            "properties": {
                "id": stop.get("id", ""),
                "name": stop.get("commonName", ""),
                "modes": stop.get("modes", []),
                "zone": stop.get("zone", ""),
            },
        })

    geojson = {"type": "FeatureCollection", "features": features}
    dest.write_text(json.dumps(geojson), encoding="utf-8")
    print(
        f"  [done] Saved {dest.name} "
        f"({len(features)} stations from {page} page(s))"
    )
    return dest


# ── 2. IMD 2019 scores ─────────────────────────────────────────────────────

def download_imd_scores() -> Path:
    """Download IMD 2019 — all scores, ranks, deciles & population (CSV).

    Source: File 7 from the English Indices of Deprivation 2019, published by
    MHCLG on gov.uk.  This CSV contains ~32,844 rows (one per LSOA in England)
    with the overall IMD score, all domain scores, ranks, deciles, and
    population denominators.

    Verified: HTTP 200, text/csv (March 2026).

    NOTE: The English Indices of Deprivation 2025 (IoD25) were published in
    October 2025.  If you need the latest deprivation data, see:
        https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025
    The IoD25 uses 2021 LSOA geography (33,755 LSOAs) whereas IoD2019 uses
    2011 LSOA geography (32,844 LSOAs).
    """
    url = (
        "https://assets.publishing.service.gov.uk/media/"
        "5dc407b440f0b6379a7acc8d/"
        "File_7_-_All_IoD2019_Scores__Ranks__Deciles_and_"
        "Population_Denominators_3.csv"
    )
    dest = DATA_RAW / IMD_CSV
    return _download_file(url, dest, "IMD 2019 scores (File 7, CSV)")


# ── 3. Crowding (station entry/exit counts) ─────────────────────────────────

def download_crowding_data() -> Path:
    """Download station entry/exit crowding data from TfL open data.

    The Annual Station Counts data lives at:
        https://crowding.data.tfl.gov.uk/Annual%20Station%20Counts/{year}/

    Verified: 2023 file → HTTP 200, application/vnd...spreadsheetml (March 2026).
    The 2024 file (.xlsm) was briefly indexed but now returns 404.
    Change _CROWDING_YEAR at the top of this module to target a different year.
    """
    url = (
        f"https://crowding.data.tfl.gov.uk/"
        f"Annual%20Station%20Counts/"
        f"{_CROWDING_YEAR}/{_CROWDING_FILENAME}"
    )
    dest = DATA_RAW / CROWDING_XLSX
    return _download_file(
        url, dest, f"Station crowding entry/exit ({_CROWDING_YEAR})"
    )


# ── 4. London LSOA boundaries ──────────────────────────────────────────────

def download_lsoa_boundaries() -> Path:
    """Download London LSOA 2011 boundary shapefiles from London Datastore.

    Downloads a ZIP containing ESRI shapefiles for OA, LSOA, MSOA, Wards, and
    Boroughs.  We extract the LSOA_2011_London_gen_MHW shapefile components
    into data/raw/.

    Source: data.london.gov.uk/dataset/statistical-gis-boundary-files-london
    The ZIP URL is used in many active projects and is the canonical source for
    London-specific LSOA boundaries (4,835 LSOAs, 2011 geography — matches
    IMD 2019).

    NOTE: This is a ~25 MB download.  If it fails due to timeout, download
    manually from the London Datastore page above.
    """
    # Check if already extracted
    dest_dir = DATA_RAW / "statistical-gis-boundaries-london"
    marker = DATA_RAW / "LSOA_2011_London_gen_MHW.shp"
    if marker.exists() or dest_dir.exists():
        print(f"  [skip] LSOA boundaries already exist")
        return marker if marker.exists() else dest_dir

    url = (
        "https://data.london.gov.uk/download/"
        "statistical-gis-boundary-files-london/"
        "9ba8c833-6370-4b11-abdc-314aa020d5e0/"
        "statistical-gis-boundaries-london.zip"
    )

    print("  [download] London LSOA boundaries (London Datastore ZIP) ...")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    # Extract shapefile components for LSOA 2011
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        lsoa_prefix = "statistical-gis-boundaries-london/ESRI/LSOA_2011_London_gen_MHW"
        extracted = []
        for name in zf.namelist():
            if name.startswith(lsoa_prefix):
                # Extract to DATA_RAW with flat filename
                fname = Path(name).name
                out = DATA_RAW / fname
                out.write_bytes(zf.read(name))
                extracted.append(fname)

    print(f"  [done] Extracted {len(extracted)} LSOA boundary files")
    return DATA_RAW / "LSOA_2011_London_gen_MHW.shp"


# ── download_all ────────────────────────────────────────────────────────────

def download_all() -> dict[str, Path]:
    """Download all available datasets. Returns dict of name → path."""
    print("=" * 60)
    print("Downloading datasets with stable URLs")
    print("=" * 60)

    results = {}
    downloaders = [
        ("stations", download_station_locations),
        ("imd", download_imd_scores),
        ("crowding", download_crowding_data),
        ("lsoa_boundaries", download_lsoa_boundaries),
    ]

    for name, fn in downloaders:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            results[name] = None

    print("=" * 60)
    ok = sum(1 for v in results.values() if v is not None)
    print(f"Downloaded {ok}/{len(results)} datasets.")
    print("\nManual downloads still needed (see README.md):")
    print("  - PTAL grid 2023 (TfL GIS Open Data Hub)")
    print("    https://gis-tfl.opendata.arcgis.com/datasets/0646faf45243463aa04ca685e598f471")
    print("    Or use LSOA-aggregated version (saves spatial join):")
    print("    https://gis-tfl.opendata.arcgis.com/datasets/3eb38b75667a49df9ef1240e9a197615")
    print("  - Census 2021 population & economic activity (NOMIS bulk)")
    print("    https://www.nomisweb.co.uk/sources/census_2021_bulk")
    print("=" * 60)
    return results

if __name__ == "__main__":
    download_all()