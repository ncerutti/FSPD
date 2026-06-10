"""
Extract policy data from FAPDA's public web endpoints.

Usage:
    python fetch_fapda_data.py
    python fetch_fapda_data.py --resource decisions --limit 500
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


DEFAULT_BASE_URL = "https://fapda.apps.fao.org/fapda/"
DEFAULT_OUTPUT_DIR = Path("data/raw/fapda")


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    path: str
    search_fields: tuple[str, ...]


DECISIONS_ENDPOINT = EndpointSpec(
    name="policy_decisions",
    path="policydecision/searchpolicies",
    search_fields=(
        "countryIds",
        "subregionIds",
        "policyMeasureCodes",
        "foodSecIds",
        "commodityCodes",
        "policyDecisionG20Ids",
        "initialFromDate",
        "includeEmptyInitialDate",
        "initialToDate",
        "freeText",
    ),
)

FRAMEWORKS_ENDPOINT = EndpointSpec(
    name="policy_frameworks",
    path="policyframeworks/",
    search_fields=(
        "countryIds",
        "subregionIds",
        "policyFrameworkClassificationIds",
        "initialFromDate",
        "policyFrameworkSDGIds",
        "policyFrameworkG20Ids",
        "policyFrameworkRoadmapIds",
        "selectedQUIPD",
        "includeEmptyInitialDate",
        "initialToDate",
        "freeText",
    ),
)


class FAPDAClient:
    def __init__(
        self,
        base_url: str,
        timeout: int = 60,
        max_retries: int = 5,
        retry_backoff: float = 1.5,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "FSPD-FAPDA-ETL/1.0",
                "Accept": "application/json",
            }
        )

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = self.base_url + path
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_backoff ** attempt)

        raise RuntimeError(f"Failed to fetch {url}") from last_error

    @staticmethod
    def _build_params(spec: EndpointSpec, start: int, length: int, draw: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "draw": draw,
            "start": start,
            "length": length,
            "idPolicy": "",
        }
        for field in spec.search_fields:
            params[f"policySearch[{field}]"] = ""
        return params

    def fetch_all(
        self,
        spec: EndpointSpec,
        page_size: int,
        limit: int | None = None,
        sleep_seconds: float = 0.0,
        skip_on_error: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if page_size <= 0:
            raise ValueError("page_size must be > 0")

        records: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        expected_total: int | None = None
        start = 0
        draw = 1

        while True:
            if limit is not None and start >= limit:
                break

            length = page_size if limit is None else min(page_size, limit - start)
            params = self._build_params(spec, start=start, length=length, draw=draw)
            try:
                payload = self._request_json(spec.path, params)
            except RuntimeError as exc:
                if not skip_on_error:
                    raise
                print(f"[{spec.name}] WARNING: skipping page at offset {start} ({exc})")
                start += page_size
                draw += 1
                continue
            batch = payload.get("ResourceList")
            if not isinstance(batch, list):
                raise RuntimeError(
                    f"Unexpected response format for {spec.name}: 'ResourceList' is not a list"
                )

            if expected_total is None:
                total_value = payload.get("recordsFiltered", payload.get("recordsTotal", 0))
                expected_total = int(total_value) if total_value is not None else 0
                metadata = {
                    key: value
                    for key, value in payload.items()
                    if key not in {"ResourceList"}
                }

            if not batch:
                break

            records.extend(batch)
            start += len(batch)
            draw += 1

            print(f"[{spec.name}] fetched {start}" + (f"/{expected_total}" if expected_total else ""))

            if limit is not None and start >= limit:
                records = records[:limit]
                break

            if expected_total and start >= expected_total:
                break

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        return records, metadata


def deduplicate_by_id(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    removed = 0

    for record in records:
        record_id = record.get("id")
        if record_id is None:
            deduped.append(record)
            continue

        record_id_str = str(record_id)
        if record_id_str in seen_ids:
            removed += 1
            continue
        seen_ids.add(record_id_str)
        deduped.append(record)

    return deduped, removed


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_flat_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "CSV export requires pandas. Install dependencies or run with --no_csv."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = pd.json_normalize(records, sep="_")
    dataframe.to_csv(output_path, index=False)


def run_export(
    client: FAPDAClient,
    endpoint: EndpointSpec,
    output_dir: Path,
    page_size: int,
    limit: int | None,
    sleep_seconds: float,
    write_csv: bool,
    skip_on_error: bool = False,
) -> dict[str, Any]:
    records, api_metadata = client.fetch_all(
        endpoint,
        page_size=page_size,
        limit=limit,
        sleep_seconds=sleep_seconds,
        skip_on_error=skip_on_error,
    )
    records, duplicates_removed = deduplicate_by_id(records)

    jsonl_path = output_dir / f"fapda_{endpoint.name}.jsonl"
    write_jsonl(records, jsonl_path)

    csv_path: Path | None = None
    if write_csv:
        csv_path = output_dir / f"fapda_{endpoint.name}.csv"
        write_flat_csv(records, csv_path)

    summary: dict[str, Any] = {
        "endpoint": endpoint.path,
        "records": len(records),
        "duplicates_removed": duplicates_removed,
        "jsonl_path": str(jsonl_path),
        "api_records_total": api_metadata.get("recordsTotal"),
        "api_records_filtered": api_metadata.get("recordsFiltered"),
    }
    if csv_path is not None:
        summary["csv_path"] = str(csv_path)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch FAPDA data for FSPD ETL.")
    parser.add_argument(
        "--resource",
        choices=["decisions", "frameworks", "both"],
        default="both",
        help="Which FAPDA resources to fetch.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for exported files (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--page_size",
        type=int,
        default=1000,
        help="Pagination size per request (default: 1000).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on records per resource.",
    )
    parser.add_argument(
        "--base_url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"FAPDA base URL (default: {DEFAULT_BASE_URL}).",
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
        "--sleep_seconds",
        type=float,
        default=0.0,
        help="Optional sleep between paginated requests.",
    )
    parser.add_argument(
        "--no_csv",
        action="store_true",
        help="Skip flattened CSV exports and write only JSONL.",
    )
    parser.add_argument(
        "--skip_on_error",
        action="store_true",
        help="Skip pages that fail JSON parsing instead of aborting (e.g. corrupted server response).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    endpoints: list[EndpointSpec]
    if args.resource == "decisions":
        endpoints = [DECISIONS_ENDPOINT]
    elif args.resource == "frameworks":
        endpoints = [FRAMEWORKS_ENDPOINT]
    else:
        endpoints = [DECISIONS_ENDPOINT, FRAMEWORKS_ENDPOINT]

    client = FAPDAClient(
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    run_started_at = datetime.now(tz=timezone.utc).isoformat()
    all_summaries: dict[str, Any] = {}

    for endpoint in endpoints:
        summary = run_export(
            client=client,
            endpoint=endpoint,
            output_dir=args.output_dir,
            page_size=args.page_size,
            limit=args.limit,
            sleep_seconds=args.sleep_seconds,
            write_csv=not args.no_csv,
            skip_on_error=args.skip_on_error,
        )
        all_summaries[endpoint.name] = summary
        print(
            f"[{endpoint.name}] saved {summary['records']} records to {summary['jsonl_path']}"
        )

    metadata_path = args.output_dir / "fapda_etl_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "fetched_at_utc": run_started_at,
                "base_url": args.base_url,
                "resource": args.resource,
                "page_size": args.page_size,
                "limit": args.limit,
                "summaries": all_summaries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Metadata written to {metadata_path}")


if __name__ == "__main__":
    main()
