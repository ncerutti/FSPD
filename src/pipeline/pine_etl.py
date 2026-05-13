"""
Extract OECD PINE-related data through the public OECD SDMX REST API.

Usage:
    python fetch_pine_data.py
    python fetch_pine_data.py --flow_id DSD_CAPMF@DF_CAPMF --flow_id DSD_ERTR@DF_ERTR
    python fetch_pine_data.py --list_flows
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_OUTPUT_DIR = Path("data/raw/pine")
FLOWS_ENDPOINT = "https://sdmx.oecd.org/public/rest/dataflow/OECD.ENV.EPI"
DATA_ENDPOINT_TEMPLATE = "https://sdmx.oecd.org/public/rest/data/OECD.ENV.EPI,{flow_id},{version}/all"
DEFAULT_FLOW_IDS = [
    "DSD_CAPMF@DF_CAPMF",
    "DSD_ERTR@DF_ERTR",
    "DSD_ERTR@DF_ERTR_ACC",
]


@dataclass(frozen=True)
class Dataflow:
    id: str
    version: str
    agency_id: str
    name: str


class HTTPClient:
    def __init__(self, timeout: int = 90, max_retries: int = 5, retry_backoff: float = 1.5):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "FSPD-PINE-SDMX-ETL/1.0"})

    def get_json(
        self,
        url: str,
        accept: str,
        params: dict[str, Any] | None = None,
        allow_no_records_404: bool = False,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    headers={"Accept": accept},
                    params=params,
                    timeout=self.timeout,
                )
                if response.status_code == 404 and allow_no_records_404:
                    if "NoRecordsFound" in response.text:
                        return {"meta": {"message": "NoRecordsFound"}, "dataSets": [], "structure": {}}
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


def safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _value_label(value_obj: dict[str, Any]) -> str:
    if "id" in value_obj and value_obj["id"] is not None:
        return str(value_obj["id"])
    if "name" in value_obj and value_obj["name"] is not None:
        return str(value_obj["name"])
    names = value_obj.get("names")
    if isinstance(names, dict):
        return str(names.get("en") or next(iter(names.values()), ""))
    return ""


def _extract_indexed_value(values: list[dict[str, Any]], index: int | None) -> tuple[str, str]:
    if index is None or index < 0 or index >= len(values):
        return "", ""
    value_obj = values[index]
    value_id = str(value_obj.get("id", ""))
    value_label = _value_label(value_obj)
    return value_id, value_label


def flatten_sdmx_data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    data_sets = payload.get("dataSets", [])
    structure = payload.get("structure", {})
    dimensions = structure.get("dimensions", {})
    attributes = structure.get("attributes", {})

    if not data_sets:
        return rows

    data_set = data_sets[0]
    series_dims = dimensions.get("series", []) or []
    obs_dims = dimensions.get("observation", []) or []
    series_attrs = attributes.get("series", []) or []
    obs_attrs = attributes.get("observation", []) or []

    # Common case: SDMX data grouped in series with series-level + observation-level dims.
    if isinstance(data_set.get("series"), dict):
        for series_key, series_obj in data_set["series"].items():
            series_indices = [int(x) for x in series_key.split(":")] if series_key else []
            base_row: dict[str, Any] = {}

            for dim_obj, dim_idx in zip(series_dims, series_indices):
                dim_id = dim_obj.get("id", "")
                value_id, value_label = _extract_indexed_value(dim_obj.get("values", []), dim_idx)
                base_row[dim_id] = value_id
                base_row[f"{dim_id}_label"] = value_label

            series_attr_indices = series_obj.get("attributes", []) if isinstance(series_obj, dict) else []
            for attr_obj, attr_idx in zip(series_attrs, series_attr_indices):
                attr_id = attr_obj.get("id", "")
                value_id, value_label = _extract_indexed_value(attr_obj.get("values", []), attr_idx)
                base_row[f"series_attr_{attr_id}"] = value_id
                base_row[f"series_attr_{attr_id}_label"] = value_label

            observations = series_obj.get("observations", {}) if isinstance(series_obj, dict) else {}
            for obs_key, obs_values in observations.items():
                row = dict(base_row)
                obs_indices = [int(x) for x in obs_key.split(":")] if obs_key else []
                for dim_obj, dim_idx in zip(obs_dims, obs_indices):
                    dim_id = dim_obj.get("id", "")
                    value_id, value_label = _extract_indexed_value(dim_obj.get("values", []), dim_idx)
                    row[dim_id] = value_id
                    row[f"{dim_id}_label"] = value_label

                if isinstance(obs_values, list):
                    row["value"] = obs_values[0] if obs_values else None
                    obs_attr_indices = obs_values[1:]
                    for attr_obj, attr_idx in zip(obs_attrs, obs_attr_indices):
                        attr_id = attr_obj.get("id", "")
                        value_id, value_label = _extract_indexed_value(attr_obj.get("values", []), attr_idx)
                        row[f"obs_attr_{attr_id}"] = value_id
                        row[f"obs_attr_{attr_id}_label"] = value_label
                else:
                    row["value"] = obs_values

                rows.append(row)
        return rows

    # Fallback for datasets exposed directly in observation map.
    observations = data_set.get("observations", {})
    if isinstance(observations, dict):
        for obs_key, obs_values in observations.items():
            row: dict[str, Any] = {}
            obs_indices = [int(x) for x in obs_key.split(":")] if obs_key else []
            for dim_obj, dim_idx in zip(obs_dims, obs_indices):
                dim_id = dim_obj.get("id", "")
                value_id, value_label = _extract_indexed_value(dim_obj.get("values", []), dim_idx)
                row[dim_id] = value_id
                row[f"{dim_id}_label"] = value_label

            if isinstance(obs_values, list):
                row["value"] = obs_values[0] if obs_values else None
            else:
                row["value"] = obs_values
            rows.append(row)

    return rows


def extract_data_message(payload: dict[str, Any]) -> dict[str, Any]:
    data_obj = payload.get("data")
    if isinstance(data_obj, dict) and ("dataSets" in data_obj or "structure" in data_obj):
        return data_obj
    return payload


def parse_dataflows(payload: dict[str, Any]) -> dict[str, Dataflow]:
    flows = payload.get("data", {}).get("dataflows", [])
    parsed: dict[str, Dataflow] = {}
    for flow in flows:
        flow_id = str(flow.get("id", ""))
        if not flow_id:
            continue
        parsed[flow_id] = Dataflow(
            id=flow_id,
            version=str(flow.get("version", "1.0")),
            agency_id=str(flow.get("agencyID", "")),
            name=str(flow.get("name", flow_id)),
        )
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch PINE-related OECD datasets via SDMX REST (source referenced by the PINE platform)."
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for outputs (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--flow_id",
        action="append",
        default=None,
        help="Flow ID to fetch (repeatable). Example: --flow_id DSD_CAPMF@DF_CAPMF",
    )
    parser.add_argument(
        "--list_flows",
        action="store_true",
        help="Only list available OECD.ENV.EPI flow IDs and exit.",
    )
    parser.add_argument(
        "--start_period",
        type=str,
        default=None,
        help="Optional SDMX startPeriod filter (e.g. 2010).",
    )
    parser.add_argument(
        "--end_period",
        type=str,
        default=None,
        help="Optional SDMX endPeriod filter (e.g. 2025).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="HTTP timeout in seconds (default: 90).",
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

    flows_payload = client.get_json(
        FLOWS_ENDPOINT,
        accept="application/vnd.sdmx.structure+json;version=1.0.0-wd",
    )
    flows = parse_dataflows(flows_payload if isinstance(flows_payload, dict) else {})

    if args.list_flows:
        print("Available OECD.ENV.EPI flow IDs:")
        for flow in sorted(flows.values(), key=lambda f: f.id):
            print(f"{flow.id} ({flow.version}) - {flow.name}")
        return

    target_flow_ids = args.flow_id if args.flow_id else list(DEFAULT_FLOW_IDS)
    missing_flow_ids = [flow_id for flow_id in target_flow_ids if flow_id not in flows]
    if missing_flow_ids:
        raise RuntimeError(
            "Unknown flow_id(s): " + ", ".join(missing_flow_ids) + ". Run with --list_flows."
        )

    summaries: dict[str, Any] = {}

    for flow_id in target_flow_ids:
        flow = flows[flow_id]
        params: dict[str, Any] = {}
        if args.start_period:
            params["startPeriod"] = args.start_period
        if args.end_period:
            params["endPeriod"] = args.end_period

        endpoint = DATA_ENDPOINT_TEMPLATE.format(flow_id=flow.id, version=flow.version)
        data_payload = client.get_json(
            endpoint,
            accept="application/vnd.sdmx.data+json;version=1.0.0-wd",
            params=params if params else None,
            allow_no_records_404=True,
        )
        data_message = extract_data_message(data_payload if isinstance(data_payload, dict) else {})
        records = flatten_sdmx_data(data_message)

        flow_slug = safe_name(flow.id)
        raw_json_path = output_dir / f"pine_{flow_slug}_raw.json"
        jsonl_path = output_dir / f"pine_{flow_slug}_records.jsonl"
        write_json(data_payload, raw_json_path)
        write_jsonl(records, jsonl_path)

        csv_path: str | None = None
        if not args.no_csv:
            csv_file = output_dir / f"pine_{flow_slug}_records.csv"
            write_csv(records, csv_file)
            csv_path = str(csv_file)

        summaries[flow.id] = {
            "name": flow.name,
            "version": flow.version,
            "agency_id": flow.agency_id,
            "endpoint": endpoint,
            "params": params,
            "records": len(records),
            "raw_json_path": str(raw_json_path),
            "jsonl_path": str(jsonl_path),
            "csv_path": csv_path,
        }
        print(f"[{flow.id}] saved {len(records)} records")

    metadata = {
        "fetched_at_utc": started_at,
        "source": "https://oecd-main.shinyapps.io/pinedatabase/",
        "source_mode": "oecd_sdmx_rest",
        "dataflow_endpoint": FLOWS_ENDPOINT,
        "flows": summaries,
    }
    metadata_path = output_dir / "pine_etl_metadata.json"
    write_json(metadata, metadata_path)
    print(f"Metadata written to {metadata_path}")


if __name__ == "__main__":
    main()
