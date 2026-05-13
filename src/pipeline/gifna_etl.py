"""
Extract publicly available GIFNA data assets.

Usage:
    python fetch_gifna_data.py
    python fetch_gifna_data.py --skip_boundaries --no_csv
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_OUTPUT_DIR = Path("data/raw/gifna")
MAP_DATA_URL = "https://gifna.who.int/json/mapData.json"
DISPUTED_AREAS_URL = "https://gifna.who.int/json/disputed.json"
WHO_BOUNDARIES_URL = (
    "https://extranet.who.int/map/rest/services/GISC/WHO_ADMIN_BOUNDARIES/MapServer/0/query"
    "?where=1%3D1&outFields=ISO_2_CODE,STARTDATE,ENDDATE,ISO_3_CODE,WHO_REGION,WHO_CODE,WHO_STATUS"
    "&outSR=4326&f=json"
)


class HTTPClient:
    def __init__(self, timeout: int = 60, max_retries: int = 5, retry_backoff: float = 1.5):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "FSPD-GIFNA-ETL/1.0",
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def get_json(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_backoff ** attempt)
        raise RuntimeError(f"Failed to fetch JSON from {url}") from last_error


def write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(records: list[dict[str, Any]], path: Path) -> None:
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError("CSV export requires pandas. Install dependencies or use --no_csv.") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = pd.json_normalize(records, sep="_")
    dataframe.to_csv(path, index=False)


def map_counts_records(map_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, entries in map_payload.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, list) or len(entry) < 3:
                continue
            iso2, country, action_count = entry[0], entry[1], entry[2]
            rows.append(
                {
                    "bucket": bucket,
                    "iso2": iso2,
                    "country": country,
                    "action_count": action_count,
                }
            )
    return rows


def disputed_areas_summary(disputed_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for area_name, geometry in disputed_payload.items():
        rings = geometry.get("rings", []) if isinstance(geometry, dict) else []
        ring_count = len(rings) if isinstance(rings, list) else 0
        point_count = 0
        if isinstance(rings, list):
            for ring in rings:
                if isinstance(ring, list):
                    point_count += len(ring)
        rows.append(
            {
                "area_name": area_name,
                "ring_count": ring_count,
                "point_count": point_count,
            }
        )
    return rows


def boundaries_records(boundaries_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in boundaries_payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        attributes = feature.get("attributes", {})
        if isinstance(attributes, dict):
            rows.append(attributes)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch GIFNA public data assets.")
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for outputs (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--skip_boundaries",
        action="store_true",
        help="Skip WHO ArcGIS boundaries export.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds (default: 60).",
    )
    parser.add_argument(
        "--max_retries",
        type=int,
        default=5,
        help="Retry count on transient HTTP/JSON errors (default: 5).",
    )
    parser.add_argument(
        "--retry_backoff",
        type=float,
        default=1.5,
        help="Retry backoff multiplier (default: 1.5).",
    )
    parser.add_argument(
        "--no_csv",
        action="store_true",
        help="Skip CSV exports and write JSON/JSONL only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(tz=timezone.utc).isoformat()

    client = HTTPClient(
        timeout=args.timeout,
        max_retries=args.max_retries,
        retry_backoff=args.retry_backoff,
    )
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) GIFNA map counts by country bucket
    map_payload = client.get_json(MAP_DATA_URL)
    map_rows = map_counts_records(map_payload if isinstance(map_payload, dict) else {})
    map_raw_path = output_dir / "gifna_map_data_raw.json"
    map_jsonl_path = output_dir / "gifna_map_data_records.jsonl"
    write_json(map_payload, map_raw_path)
    write_jsonl(map_rows, map_jsonl_path)
    map_csv_path: str | None = None
    if not args.no_csv:
        map_csv = output_dir / "gifna_map_data_records.csv"
        write_csv(map_rows, map_csv)
        map_csv_path = str(map_csv)
    print(f"[gifna_map_data] saved {len(map_rows)} records")

    # 2) Disputed geometry metadata used in GIFNA map rendering
    disputed_payload = client.get_json(DISPUTED_AREAS_URL)
    disputed_rows = disputed_areas_summary(disputed_payload if isinstance(disputed_payload, dict) else {})
    disputed_raw_path = output_dir / "gifna_disputed_areas_raw.json"
    disputed_jsonl_path = output_dir / "gifna_disputed_areas_summary.jsonl"
    write_json(disputed_payload, disputed_raw_path)
    write_jsonl(disputed_rows, disputed_jsonl_path)
    disputed_csv_path: str | None = None
    if not args.no_csv:
        disputed_csv = output_dir / "gifna_disputed_areas_summary.csv"
        write_csv(disputed_rows, disputed_csv)
        disputed_csv_path = str(disputed_csv)
    print(f"[gifna_disputed_areas] saved {len(disputed_rows)} records")

    boundaries_summary: dict[str, Any] | None = None
    if not args.skip_boundaries:
        boundaries_payload = client.get_json(WHO_BOUNDARIES_URL)
        boundary_rows = boundaries_records(boundaries_payload if isinstance(boundaries_payload, dict) else {})
        boundaries_raw_path = output_dir / "gifna_who_boundaries_raw.json"
        boundaries_jsonl_path = output_dir / "gifna_who_boundaries_records.jsonl"
        write_json(boundaries_payload, boundaries_raw_path)
        write_jsonl(boundary_rows, boundaries_jsonl_path)
        boundaries_csv_path: str | None = None
        if not args.no_csv:
            boundaries_csv = output_dir / "gifna_who_boundaries_records.csv"
            write_csv(boundary_rows, boundaries_csv)
            boundaries_csv_path = str(boundaries_csv)
        boundaries_summary = {
            "records": len(boundary_rows),
            "source_url": WHO_BOUNDARIES_URL,
            "raw_json_path": str(boundaries_raw_path),
            "jsonl_path": str(boundaries_jsonl_path),
            "csv_path": boundaries_csv_path,
        }
        print(f"[gifna_who_boundaries] saved {len(boundary_rows)} records")

    metadata = {
        "fetched_at_utc": started_at,
        "source": "https://gifna.who.int/search",
        "assets": {
            "map_data": {
                "records": len(map_rows),
                "source_url": MAP_DATA_URL,
                "raw_json_path": str(map_raw_path),
                "jsonl_path": str(map_jsonl_path),
                "csv_path": map_csv_path,
            },
            "disputed_areas": {
                "records": len(disputed_rows),
                "source_url": DISPUTED_AREAS_URL,
                "raw_json_path": str(disputed_raw_path),
                "jsonl_path": str(disputed_jsonl_path),
                "csv_path": disputed_csv_path,
            },
            "who_boundaries": boundaries_summary,
        },
    }
    metadata_path = output_dir / "gifna_etl_metadata.json"
    write_json(metadata, metadata_path)
    print(f"Metadata written to {metadata_path}")


if __name__ == "__main__":
    main()

