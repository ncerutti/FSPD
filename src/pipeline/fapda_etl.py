"""
Extract policy data from FAPDA's public export API.

June 2026: FAO replaced the old DataTables JSON API
(https://fapda.apps.fao.org/fapda/...searchpolicies, now permanently dead)
with a Next.js site backed by a Google Cloud Run API. The site's "Download
results" button hits a single export endpoint that returns the whole dataset
as one xlsx — the same file a user downloads from the website. This fetcher
uses that endpoint directly: no pagination, no window bisection.

Usage:
    python fetch_fapda_data.py
    python fetch_fapda_data.py --resource decisions --limit 500
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


# Google Cloud Run backend that powers https://fapda.apps.fao.org/
DEFAULT_BASE_URL = "https://fapda.apps.fao.org"
DEFAULT_OUTPUT_DIR = Path("data/fapda")

# Headers the website sends; the backend is CORS-scoped to the FAPDA origin.
_REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    "Origin": "https://fapda.apps.fao.org",
    "Referer": "https://fapda.apps.fao.org/",
    "User-Agent": "FSPD-FAPDA-ETL/2.0",
}

# xlsx files are zip archives: they always start with the "PK" magic bytes.
_XLSX_MAGIC = b"PK"
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class EndpointSpec:
    name: str            # output file stem
    resource: str        # API resource path segment
    output_name: str     # data file name (without extension handled below)


DECISIONS_ENDPOINT = EndpointSpec(
    name="policy_decisions",
    resource="policy-decision",
    output_name="fapda_policy_decisions",
)

FRAMEWORKS_ENDPOINT = EndpointSpec(
    name="policy_frameworks",
    resource="policy-framework",
    output_name="fapda_policy_frameworks",
)


class FAPDAClient:
    def __init__(self, base_url: str, timeout: int = 180, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(_REQUEST_HEADERS)

    def _api_url(self, resource: str, suffix: str = "") -> str:
        return f"{self.base_url}/api/v1/tool/{resource}{suffix}"

    def fetch_total(self, spec: EndpointSpec) -> int | None:
        """Best-effort record count from the JSON list endpoint (sanity check)."""
        url = self._api_url(spec.resource)
        try:
            resp = self.session.post(
                url, params={"page": 1, "per_page": 1}, json={}, timeout=self.timeout
            )
            resp.raise_for_status()
            payload = resp.json()
            total = payload.get("total")
            return int(total) if total is not None else None
        except (requests.RequestException, ValueError):
            return None

    def download_xlsx(self, spec: EndpointSpec, output_path: Path) -> int:
        """Stream the full export to output_path. Fail fast if it is not an
        xlsx. Returns the byte size written."""
        url = self._api_url(spec.resource, "/download")
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with self.session.post(
                    url, json={}, timeout=self.timeout, stream=True
                ) as resp:
                    resp.raise_for_status()
                    content_type = resp.headers.get("Content-Type", "")
                    chunks = resp.iter_content(chunk_size=65536)
                    first = next(chunks, b"")
                    if not first.startswith(_XLSX_MAGIC):
                        raise RuntimeError(
                            f"FAPDA export did not return an xlsx (got "
                            f"'{content_type or 'unknown content-type'}'); the API "
                            f"may have moved again — see docs/fetching.md"
                        )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    size = 0
                    with output_path.open("wb") as fh:
                        fh.write(first)
                        size += len(first)
                        for chunk in chunks:
                            fh.write(chunk)
                            size += len(chunk)
                    return size
            except RuntimeError:
                # Wrong content (not an xlsx) is not transient — fail loudly.
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                print(
                    f"[{spec.name}] download failed "
                    f"(attempt {attempt}/{self.max_retries}): "
                    f"{type(exc).__name__}; retrying"
                )
        raise RuntimeError(f"Failed to download FAPDA {spec.name} from {url}") from last_error


def _row_count(path: Path) -> int:
    import pandas as pd
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return len(pd.read_excel(path, engine="openpyxl"))


def _truncate_xlsx(path: Path, limit: int) -> int:
    """Keep only the first `limit` data rows (for smoke tests). Returns new row count."""
    import pandas as pd
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(path, engine="openpyxl")
    df = df.head(limit)
    df.to_excel(path, index=False, engine="openpyxl")
    return len(df)


def run_export(
    client: FAPDAClient,
    endpoint: EndpointSpec,
    output_dir: Path,
    limit: int | None,
    write_csv: bool,
    fetch_total: bool = True,
) -> dict[str, Any]:
    output_path = output_dir / f"{endpoint.output_name}.xlsx"
    total = client.fetch_total(endpoint) if fetch_total else None
    size = client.download_xlsx(endpoint, output_path)

    rows = _row_count(output_path)
    if limit is not None and rows > limit:
        rows = _truncate_xlsx(output_path, limit)
        size = output_path.stat().st_size

    csv_path: Path | None = None
    if write_csv:
        import pandas as pd
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pd.read_excel(output_path, engine="openpyxl").to_csv(
                output_dir / f"{endpoint.output_name}.csv", index=False
            )
        csv_path = output_dir / f"{endpoint.output_name}.csv"

    summary: dict[str, Any] = {
        "endpoint": client._api_url(endpoint.resource, "/download"),
        "output_path": str(output_path),
        "bytes": size,
        "rows": rows,
        "api_total": total,
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
        "--limit",
        type=int,
        default=None,
        help="Optional cap on rows per resource (truncates the downloaded xlsx; for smoke runs).",
    )
    parser.add_argument(
        "--base_url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"FAPDA Cloud Run base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="HTTP timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--max_retries",
        type=int,
        default=3,
        help="Retry count on transient HTTP errors (default: 3).",
    )
    parser.add_argument(
        "--no_csv",
        action="store_true",
        help="Skip the flattened CSV copy and write only the xlsx.",
    )
    # Accepted for backwards compatibility with callers; no longer used by the
    # one-shot export API.
    parser.add_argument("--page_size", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--sleep_seconds", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--skip_on_error", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

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
            limit=args.limit,
            write_csv=not args.no_csv,
        )
        all_summaries[endpoint.name] = summary
        print(
            f"[{endpoint.name}] saved {summary['rows']} rows "
            f"({summary['bytes']:,} bytes) to {summary['output_path']}"
        )

    metadata_path = args.output_dir / "fapda_etl_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "fetched_at_utc": run_started_at,
                "base_url": args.base_url,
                "resource": args.resource,
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
