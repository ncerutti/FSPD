"""
Fetch record-level OECD PINE data (Policy INstruments for the Environment).

PINE has no SDMX dataflow and no static bulk-download URL. The only public
access is the Shiny application at https://pinedatabase.oecd.org/ (hosted on
oecd-main.shinyapps.io). This module speaks the Shiny/SockJS wire protocol
directly over plain HTTP (xhr-polling transport, no websockets needed):

  1. GET the app page        -> worker id (_w_<hex>) + session cookie
  2. GET _w_<w>/__token__    -> connection token
  3. POST __sockjs__/.../xhr -> open a SockJS session (robust + multiplex framing)
  4. send Shiny "init"       -> server registers download handlers and sends
                                their hrefs (session/<id>/download/<name>?w=<w>)
  5. GET the download href   -> the CSV (tab-separated), while keeping the
                                session alive with background polls

Of the app's download handlers, "downloadcsv4" (Data > Subscheme data) and
"downloadcsv3" (Data > Environmentally related tax revenue) work headlessly.
"downloadcsv1" (Data > Instrument data) errors server-side without a real
browser, so the instrument-level table is derived from the subscheme table
by deduplicating on InstrumentId (instrument attributes are constant across
subscheme rows; columns are identical apart from the extra SubSchemeId).

Usage:
    python3 fetch_pine_data.py
    python3 fetch_pine_data.py --include_ertr
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import string
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_OUTPUT_DIR = Path("data/raw/pine")
PINE_URL = "https://pinedatabase.oecd.org/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) FSPD-PINE-ETL/2.0"

SUBSCHEME_DOWNLOAD = "downloadcsv4"  # Data > Subscheme data (instrument-level + SubSchemeId)
ERTR_DOWNLOAD = "downloadcsv3"       # Data > Environmentally related tax revenue

REQUIRED_COLUMNS = ["InstrumentId", "CountryCode", "CountryName", "InstrumentType", "Status"]


class PINEFetchError(RuntimeError):
    pass


def _rand(chars: str, n: int) -> str:
    return "".join(random.choices(chars, k=n))


class ShinySession:
    """Minimal Shiny client over SockJS xhr-polling (requests only)."""

    def __init__(self, app_url: str = PINE_URL, timeout: int = 90):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._stop_keepalive = False
        self._keepalive_thread: threading.Thread | None = None

        response = self.session.get(app_url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        self.base = response.url.rstrip("/")
        match = re.search(r"_w_([0-9a-f]+)", response.text)
        if not match:
            raise PINEFetchError("Could not find Shiny worker id in app page.")
        self.worker = match.group(1)

        token_resp = self.session.get(f"{self.base}/_w_{self.worker}/__token__", timeout=timeout)
        token_resp.raise_for_status()
        token = token_resp.text.strip()

        rid = _rand(string.ascii_letters + string.digits, 18)
        server_id = f"{random.randint(0, 999):03d}"
        sockjs_session = _rand(string.ascii_lowercase + string.digits, 8)
        self.sock = (
            f"{self.base}/__sockjs__/n={rid}/t={token}/w={self.worker}/s=0/"
            f"{server_id}/{sockjs_session}"
        )

        opened = self.session.post(f"{self.sock}/xhr", timeout=timeout)
        if not opened.text.startswith("o"):
            raise PINEFetchError(f"SockJS open failed: {opened.status_code} {opened.text[:80]}")
        self._msg_id = 0

    def _send(self, payload: str) -> None:
        framed = f"{self._msg_id:X}#{payload}"
        self._msg_id += 1
        response = self.session.post(
            f"{self.sock}/xhr_send",
            data=json.dumps([framed]),
            headers={"Content-Type": "text/plain"},
            timeout=self.timeout,
        )
        if response.status_code not in (200, 204):
            raise PINEFetchError(f"SockJS send failed: {response.status_code}")

    def init(self, download_names: list[str]) -> None:
        data: dict[str, Any] = {
            ".clientdata_url_protocol": "https:",
            ".clientdata_url_hostname": requests.utils.urlparse(self.base).hostname,
            ".clientdata_url_port": "",
            ".clientdata_url_pathname": requests.utils.urlparse(self.base).path + "/",
            ".clientdata_url_search": "",
            ".clientdata_url_hash_initial": "",
            ".clientdata_url_hash": "",
            ".clientdata_pixelratio": 1,
            ".clientdata_allowDataUriScheme": True,
            # Filter inputs the download handlers depend on. Without these the
            # server returns header-only CSVs (subscheme) or errors (instrument).
            "dataset4": ["All"],
            "env_domain4": ["All"],
            "attr4": ["All"],
            "dataset3": ["All"],
            "env_domain3": ["All"],
        }
        for name in download_names:
            data[f".clientdata_output_{name}_hidden"] = False
        self._send("0|o|")
        self._send("0|m|" + json.dumps({"method": "init", "data": data}))

    def collect_download_hrefs(self, download_names: list[str], wait_seconds: int = 120) -> dict[str, str]:
        """Poll until the server has sent download hrefs for all requested names."""
        wanted = set(download_names)
        hrefs: dict[str, str] = {}
        deadline = time.time() + wait_seconds
        pattern = re.compile(r"session/[0-9a-f]+/download/([A-Za-z0-9_]+)\?w=[0-9a-f]+")
        while time.time() < deadline and wanted - set(hrefs):
            response = self.session.post(f"{self.sock}/xhr", timeout=self.timeout + 10)
            if response.text.startswith("c"):
                raise PINEFetchError(f"SockJS connection closed by server: {response.text[:120]}")
            for match in pattern.finditer(response.text):
                if match.group(1) in wanted:
                    hrefs[match.group(1)] = match.group(0)
        missing = wanted - set(hrefs)
        if missing:
            raise PINEFetchError(f"Server did not register download handler(s): {sorted(missing)}")
        return hrefs

    def _keepalive(self) -> None:
        while not self._stop_keepalive:
            try:
                self.session.post(f"{self.sock}/xhr", timeout=self.timeout + 10)
            except requests.RequestException:
                time.sleep(2)

    def download(self, href: str, destination: Path) -> dict[str, Any]:
        """Download a registered Shiny download href to a file."""
        self._stop_keepalive = False
        self._keepalive_thread = threading.Thread(target=self._keepalive, daemon=True)
        self._keepalive_thread.start()
        try:
            url = f"{self.base}/_w_{self.worker}/{href}"
            with self.session.get(url, timeout=600, stream=True) as response:
                if response.status_code != 200:
                    raise PINEFetchError(
                        f"Download failed: HTTP {response.status_code} for {href}"
                    )
                content_type = response.headers.get("Content-Type", "")
                if "html" in content_type:
                    raise PINEFetchError(f"Download returned HTML (server error) for {href}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                size = 0
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(1 << 16):
                        handle.write(chunk)
                        size += len(chunk)
                return {
                    "bytes": size,
                    "server_filename": _disposition_filename(
                        response.headers.get("Content-Disposition", "")
                    ),
                }
        finally:
            self._stop_keepalive = True


def _disposition_filename(disposition: str) -> str | None:
    match = re.search(r'filename="?([^";]+)"?', disposition)
    return match.group(1) if match else None


def fetch_downloads(
    download_names: list[str],
    output_dir: Path,
    timeout: int,
    max_retries: int,
    retry_backoff: float,
) -> dict[str, dict[str, Any]]:
    """Open a Shiny session and download the requested files, with retries."""
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            shiny = ShinySession(timeout=timeout)
            shiny.init(download_names)
            hrefs = shiny.collect_download_hrefs(download_names)
            results: dict[str, dict[str, Any]] = {}
            for name in download_names:
                raw_path = output_dir / f"pine_{name}_raw.tsv"
                info = shiny.download(hrefs[name], raw_path)
                info["raw_path"] = str(raw_path)
                results[name] = info
                print(f"[pine:{name}] downloaded {info['bytes']:,} bytes "
                      f"({info.get('server_filename')})")
            return results
        except (requests.RequestException, PINEFetchError) as exc:
            last_error = exc
            print(f"[pine] attempt {attempt}/{max_retries} failed: {exc}")
            if attempt < max_retries:
                time.sleep(retry_backoff ** attempt)
    raise PINEFetchError(f"PINE fetch failed after {max_retries} attempts") from last_error


def process_subschemes(raw_path: Path, output_dir: Path, min_rows: int) -> dict[str, Any]:
    """Validate the subscheme TSV and derive the instrument-level CSV."""
    import pandas as pd

    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(raw_path, sep="\t", dtype=str, low_memory=False)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise PINEFetchError(f"Subscheme download missing expected columns: {missing}")
    if len(frame) < min_rows:
        raise PINEFetchError(
            f"Subscheme download has only {len(frame)} rows (expected >= {min_rows})."
        )

    subscheme_csv = output_dir / "pine_subschemes.csv"
    frame.to_csv(subscheme_csv, index=False)

    instruments = frame.drop_duplicates(subset=["InstrumentId"], keep="first")
    subscheme_cols = [c for c in instruments.columns if c.startswith("SubScheme")]
    instruments = instruments.drop(columns=subscheme_cols)
    instruments_csv = output_dir / "pine_instruments.csv"
    instruments.to_csv(instruments_csv, index=False)

    print(f"[pine:subschemes] {len(frame):,} subscheme rows -> {subscheme_csv}")
    print(f"[pine:instruments] {len(instruments):,} instruments -> {instruments_csv}")
    return {
        "subscheme_rows": len(frame),
        "instrument_rows": len(instruments),
        "subscheme_csv": str(subscheme_csv),
        "instruments_csv": str(instruments_csv),
    }


def process_ertr(raw_path: Path, output_dir: Path) -> dict[str, Any]:
    import pandas as pd

    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(raw_path, sep="\t", dtype=str, low_memory=False)
    ertr_csv = output_dir / "pine_ertr.csv"
    frame.to_csv(ertr_csv, index=False)
    print(f"[pine:ertr] {len(frame):,} rows -> {ertr_csv}")
    return {"rows": len(frame), "csv_path": str(ertr_csv)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch record-level OECD PINE data via the PINE Shiny application."
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for outputs (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--include_ertr",
        action="store_true",
        help="Also fetch the environmentally related tax revenue table.",
    )
    parser.add_argument(
        "--min_rows",
        type=int,
        default=1000,
        help="Fail if the subscheme table has fewer rows than this (default: 1000).",
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
        default=3,
        help="Full-session retry count (default: 3).",
    )
    parser.add_argument(
        "--retry_backoff",
        type=float,
        default=2.0,
        help="Retry backoff multiplier (default: 2.0).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(tz=timezone.utc).isoformat()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    download_names = [SUBSCHEME_DOWNLOAD]
    if args.include_ertr:
        download_names.append(ERTR_DOWNLOAD)

    results = fetch_downloads(
        download_names,
        output_dir=output_dir,
        timeout=args.timeout,
        max_retries=args.max_retries,
        retry_backoff=args.retry_backoff,
    )

    downloads: dict[str, Any] = {}
    sub_info = results[SUBSCHEME_DOWNLOAD]
    sub_summary = process_subschemes(Path(sub_info["raw_path"]), output_dir, args.min_rows)
    downloads["instruments"] = {
        "rows": sub_summary["instrument_rows"],
        "csv_path": sub_summary["instruments_csv"],
        "raw_path": sub_info["raw_path"],
        "server_filename": sub_info.get("server_filename"),
    }
    downloads["subschemes"] = {
        "rows": sub_summary["subscheme_rows"],
        "csv_path": sub_summary["subscheme_csv"],
        "raw_path": sub_info["raw_path"],
        "server_filename": sub_info.get("server_filename"),
    }
    if args.include_ertr:
        ertr_info = results[ERTR_DOWNLOAD]
        ertr_summary = process_ertr(Path(ertr_info["raw_path"]), output_dir)
        downloads["ertr"] = {
            "rows": ertr_summary["rows"],
            "csv_path": ertr_summary["csv_path"],
            "raw_path": ertr_info["raw_path"],
            "server_filename": ertr_info.get("server_filename"),
        }

    metadata = {
        "fetched_at_utc": started_at,
        "source": PINE_URL,
        "source_mode": "shiny_sockjs_xhr",
        "downloads": downloads,
    }
    metadata_path = output_dir / "pine_etl_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Metadata written to {metadata_path}")


if __name__ == "__main__":
    main()
