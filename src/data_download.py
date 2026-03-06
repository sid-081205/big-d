"""Automated downloads for datasets with stable URLs.

Run directly:  python -m src.data_download
"""

import json
import requests
from pathlib import Path

from src.config import DATA_RAW, STATIONS_GEOJSON, IMD_CSV


def _download_file(url: str, dest: Path, description: str) -> Path:
    """Download a file if it doesn't already exist."""
    if dest.exists():
        print(f"  [skip] {description} already exists: {dest.name}")
        return dest
    print(f"  [download] {description} ...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  [done] Saved {dest.name} ({len(resp.content) / 1_048_576:.1f} MB)")
    return dest


def download_station_locations() -> Path:
    """Download TfL station locations from TfL Open Data ArcGIS REST API."""
    dest = DATA_RAW / STATIONS_GEOJSON
    if dest.exists():
        print(f"  [skip] Station locations already exist: {dest.name}")
        return dest

    print("  [download] TfL station locations (ArcGIS REST) ...")
    url = (
        "https://api.tfl.gov.uk/StopPoint/Mode/tube,dlr,overground,elizabeth-line"
        "?returnLines=false"
    )
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # Convert TfL API response to GeoJSON FeatureCollection
    features = []
    for stop in data.get("stopPoints", []):
        feature = {
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
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    dest.write_text(json.dumps(geojson), encoding="utf-8")
    print(f"  [done] Saved {dest.name} ({len(features)} stations)")
    return dest


def download_imd_scores() -> Path:
    """Download IMD 2019 — all scores, ranks, deciles & population (CSV)."""
    url = (
        "https://assets.publishing.service.gov.uk/media/"
        "5dc407b440f0b6379a7acc8d/"
        "File_7_-_All_IoD2019_Scores__Ranks__Deciles_and_Population_Denominators_3.csv"
    )
    dest = DATA_RAW / "imd_2019.csv"
    return _download_file(url, dest, "IMD 2019 scores (File 7, CSV)")


def download_all() -> dict[str, Path]:
    """Download all available datasets. Returns dict of name → path."""
    print("=" * 60)
    print("Downloading datasets with stable URLs")
    print("=" * 60)

    results = {}
    downloaders = [
        ("stations", download_station_locations),
        ("imd", download_imd_scores),
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
    print("\nManual downloads needed (see README.md):")
    print("  - LSOA boundaries (ONS Open Geography Portal)")
    print("  - PTAL grid (TfL Planning portal)")
    print("  - Census 2021 population & economic activity (NOMIS/ONS)")
    print("=" * 60)
    return results


if __name__ == "__main__":
    download_all()
