"""
Build the canonical FSPD dataset from the three original source files.

Sources (all under data/*/original/):
  FAPDA decisions  — fapda_details-202605161452.xls  (SpreadsheetML XML, ~28K rows)
  FAPDA frameworks — fapda_details-202605161451.xlsx (~13.9K rows)
  GIFNA            — GIFNA-SearchPage-policies-data-items-2026-05-16.csv (3,731 rows)
  PINE             — OECD-PINEVersion2026.csv (4,685 rows; food-filtered to ~637)

Schema changes vs original FSPD.csv:
  DROPPED  — _merge, state, count (construction artifacts)
  DROPPED  — income_group, region_wb, fsd_group, income_grp2, is_eu_country, is_eu_wide
             (World Bank enrichment; can be joined externally from any WB API)
  DROPPED  — segment, lever, inclusion, envitarget, diethealth, taxonomy, defn, itype,
             covid_mentioned, level (model outputs / annotation labels; not source data)
  ADDED    — sdg_codes, roadmap_codes, g20_codes, quipd (from FAPDA frameworks export)
  ADDED    — who_region (WHO region code from GIFNA)
  ADDED    — policy_type (GIFNA policy type; richer than policydirection for GIFNA rows)
  ADDED    — instrument_type, instrument_type_detail, pine_status, pine_domains (PINE)
  RENAMED  — policycategorycode kept; added policycategory for the human-readable label
  db values: FAPDA_decisions / FAPDA_F / GIFNA / PINE

PINE food filter: Domain_Fisheries='Yes' OR Domain_Forests='Yes' OR
                  Domain_LandDegradation='Yes'  (matches ~637 records; the original FSPD
                  had 598, difference is newer data)

Usage:
    python src/pipeline/build_dataset.py
    python src/pipeline/build_dataset.py --output data/FSPD_new.parquet --also_csv
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]

_HTML_TAG = re.compile(r"<[^>]+>")
_NBSP = re.compile(r"\xa0| |&nbsp;")


def _s(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    if s.lower() == "nan":
        return None
    # Strip HTML tags and normalise whitespace
    s = _HTML_TAG.sub(" ", s)
    s = _NBSP.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _year(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, float):
        if pd.isna(val):
            return None
        y = int(val)
        return y if 1800 < y < 2100 else None
    if isinstance(val, int):
        return val if 1800 < val < 2100 else None
    m = re.search(r"\b(1[89]\d{2}|2[01]\d{2})\b", str(val))
    return int(m.group(1)) if m else None


def _date_str(val: Any) -> str | None:
    """Format a date value as DD/MM/YYYY string, or return as-is if already string."""
    if val is None:
        return None
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return None
    s = str(val).strip()
    # ISO datetime → date only
    s = re.sub(r"T\d{2}:\d{2}:\d{2}.*", "", s)
    return s or None


def _pipe_codes(val: Any) -> str | None:
    """Return comma-separated codes string from a comma/pipe/semicolon-delimited value."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return _s(str(val).replace(";", "|").replace(",", "|"))


# ---------------------------------------------------------------------------
# FAPDA decisions — SpreadsheetML XML parser
# ---------------------------------------------------------------------------

_XLS_NS = "urn:schemas-microsoft-com:office:spreadsheet"
_XLS_COLS = [
    "country", "initialdate", "y_end_raw", "FAPDA_region", "FAPDA_subregion",
    "policycategorycode", "policycategorycode2",
    "policycategory", "policycategory2",
    "policydirection", "policyphase",
    "policydecision_details", "contextoradditionalinfo",
    "decision_making_institution", "budget", "beneficiaries",
    "commodity1", "commodity2", "commodity3", "additionalcommodities",
    "term", "targeted", "emergency", "foodsecuritydimension",
    "source1name", "source1link", "source2name", "source2link",
    "source3name", "source3link", "url",
]


def _parse_xml_row(elem: ET.Element) -> list[str | None]:
    """Parse a SpreadsheetML Row element into a list of cell values (Index-aware)."""
    cells: list[str | None] = []
    cur = 0
    for cell in elem.findall(f"{{{_XLS_NS}}}Cell"):
        idx = cell.get(f"{{{_XLS_NS}}}Index")
        if idx:
            cur = int(idx) - 1
        data = cell.find(f"{{{_XLS_NS}}}Data")
        while len(cells) < cur:
            cells.append(None)
        cells.append(data.text if data is not None else None)
        cur += 1
    return cells


def _fapda_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"policydecisionid=(\d+)", url)
    return m.group(1) if m else None


def load_fapda_decisions(path: Path) -> pd.DataFrame:
    print(f"Parsing FAPDA decisions XML: {path.name} …")
    rows: list[dict[str, Any]] = []
    row_num = 0
    for event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag != f"{{{_XLS_NS}}}Row":
            continue
        row_num += 1
        vals = _parse_xml_row(elem)
        elem.clear()
        if row_num == 1:  # skip header
            continue
        # Pad to expected columns
        while len(vals) < len(_XLS_COLS):
            vals.append(None)
        rec = dict(zip(_XLS_COLS, vals))

        url = _s(rec.get("url"))
        fapda_id = _fapda_id_from_url(url)
        if not fapda_id:
            continue  # skip rows without a valid URL

        # Merge dual policy codes/categories
        codes = [_s(rec.get("policycategorycode")), _s(rec.get("policycategorycode2"))]
        cats  = [_s(rec.get("policycategory")), _s(rec.get("policycategory2"))]
        code_str = "|".join(c for c in codes if c) or None
        cat_str  = "|".join(c for c in cats  if c) or None

        init = _date_str(rec.get("initialdate"))
        rows.append({
            "id":                      fapda_id,
            "db":                      "FAPDA_decisions",
            "country":                 _s(rec.get("country")),
            "iso":                     None,  # not in this export; filled from lookup below
            "policy_description":      cat_str,   # best short title available
            "policydecision_details":  _s(rec.get("policydecision_details")),
            "initialdate":             init,
            "y_start":                 _year(init),
            "y_end":                   _year(rec.get("y_end_raw")),
            "FAPDA_region":            _s(rec.get("FAPDA_region")),
            "FAPDA_subregion":         _s(rec.get("FAPDA_subregion")),
            "policydirection":         _s(rec.get("policydirection")),
            "policyphase":             _s(rec.get("policyphase")),
            "targeted":                _s(rec.get("targeted")),
            "emergency":               _s(rec.get("emergency")),
            "term":                    _s(rec.get("term")),
            "contextoradditionalinfo": _s(rec.get("contextoradditionalinfo")),
            "decision_making_institution": _s(rec.get("decision_making_institution")),
            "budget":                  _s(rec.get("budget")),
            "beneficiaries":           _s(rec.get("beneficiaries")),
            "policycategorycode":      code_str,
            "policycategory":          cat_str,
            "foodsecuritydimension":   _s(rec.get("foodsecuritydimension")),
            "commodity1":              _s(rec.get("commodity1")),
            "commodity2":              _s(rec.get("commodity2")),
            "commodity3":              _s(rec.get("commodity3")),
            "additionalcommodities":   _s(rec.get("additionalcommodities")),
            "source1name":             _s(rec.get("source1name")),
            "source1link":             _s(rec.get("source1link")),
            "source2name":             _s(rec.get("source2name")),
            "source2link":             _s(rec.get("source2link")),
            "source3name":             _s(rec.get("source3name")),
            "source3link":             _s(rec.get("source3link")),
            "url":                     url,
        })

    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} decision rows")
    return df


# ---------------------------------------------------------------------------
# FAPDA frameworks — Excel xlsx
# ---------------------------------------------------------------------------

def load_fapda_frameworks(path: Path) -> pd.DataFrame:
    print(f"Reading FAPDA frameworks: {path.name} …")
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = pd.read_excel(path, engine="openpyxl")

    # Consolidate policy category codes and labels (up to 10 pairs)
    code_cols  = [c for c in raw.columns if c.startswith("Policy category code")]
    label_cols = [c for c in raw.columns if c.startswith("Policy category") and "code" not in c.lower()]

    def _join_fw_codes(row: pd.Series) -> str | None:
        vals = [str(int(v)) for v in row[code_cols].dropna() if v != 0]
        return "|".join(vals) or None

    def _join_fw_labels(row: pd.Series) -> str | None:
        vals = [_s(v) for v in row[label_cols] if _s(v) and str(v).lower() != "nan"]
        return "|".join(vals) or None

    rows = []
    for _, r in raw.iterrows():
        fw_id = _s(r.get("ID"))
        url   = _s(r.get("Url"))
        rows.append({
            "id":                         fw_id,
            "db":                         "FAPDA_F",
            "country":                    _s(r.get("Country")),
            "iso":                        _s(r.get("ISO3")),
            "policy_description":         _s(r.get("Title")),
            "policydecision_details":     _s(r.get("Description")),
            "initialdate":                _date_str(r.get("Date of adoption")),
            "y_start":                    _year(r.get("From date")),
            "y_end":                      _year(r.get("To date")),
            "FAPDA_region":               _s(r.get("Region")),
            "FAPDA_subregion":            _s(r.get("Subregion")),
            "policydirection":            _s(r.get("Type of policy document")),
            "contextoradditionalinfo":    _s(r.get("Additional information")),
            "decision_making_institution": _s(r.get("Source name")),
            "policycategorycode":         _join_fw_codes(r),
            "policycategory":             _join_fw_labels(r),
            "sdg_codes":                  _pipe_codes(r.get("SDGs")),
            "roadmap_codes":              _pipe_codes(r.get("ROADMAPs")),
            "g20_codes":                  _pipe_codes(r.get("G20s")),
            "quipd":                      _s(r.get("QUIPD")),
            "gendermainstreamed":         r.get("Gender mainstreamed"),
            "nutritionmainstreamed":      r.get("Nutrition mainstreamed"),
            "source1name":                None,
            "source1link":                _s(r.get("Source link")),
            "url":                        url,
        })

    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} framework rows")
    return df


# ---------------------------------------------------------------------------
# GIFNA
# ---------------------------------------------------------------------------

def load_gifna(path: Path) -> pd.DataFrame:
    print(f"Reading GIFNA: {path.name} …")
    raw = pd.read_csv(path)

    rows = []
    for _, r in raw.iterrows():
        # Topics is pipe-separated list
        topics = _s(r.get("Topics"))

        rows.append({
            "id":                         str(int(r["Policy_Id"])),
            "db":                         "GIFNA",
            "country":                    _s(r.get("Country_Name")),
            "iso":                        _s(r.get("Iso3Code")),
            "policy_description":         _s(r.get("Policy_Title")),
            "policydecision_details":     _s(r.get("Extracts")),
            "initialdate":                _s(r.get("Published_Year")),
            "y_start":                    _year(r.get("Start_Year")),
            "y_end":                      _year(r.get("End_Year")),
            "who_region":                 _s(r.get("Region_Code")),
            "policydirection":            _s(r.get("Policy_Type")),
            "policy_type":                _s(r.get("Policy_Type")),
            "decision_making_institution": _s(r.get("Published_By")),
            "contextoradditionalinfo":    _s(r.get("Further_Notes")),
            "topics":                     topics,
            "source1link":                _s(r.get("URL")),
            "url":                        _s(r.get("URL")),
        })

    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} GIFNA rows")
    return df


# ---------------------------------------------------------------------------
# PINE
# ---------------------------------------------------------------------------

_PINE_FOOD_DOMAINS = ["Domain_Fisheries", "Domain_Forests", "Domain_LandDegradation"]


def load_pine(path: Path) -> pd.DataFrame:
    print(f"Reading PINE: {path.name} …")
    raw = pd.read_csv(path, low_memory=False)

    # Food relevance filter
    food_mask = raw[_PINE_FOOD_DOMAINS].eq("Yes").any(axis=1)
    raw = raw[food_mask].copy()
    print(f"  food filter ({' | '.join(_PINE_FOOD_DOMAINS)}): {len(raw):,} rows kept")

    domain_cols = [c for c in raw.columns if c.startswith("Domain_")]

    def _domains(row: pd.Series) -> str | None:
        yes = [c.replace("Domain_", "") for c in domain_cols if row.get(c) == "Yes"]
        return "|".join(yes) or None

    rows = []
    for _, r in raw.iterrows():
        eff_year = _year(r.get("Status_EffectiveFirstEntry_Year"))

        rows.append({
            "id":                         _s(r.get("InstrumentId")),
            "db":                         "PINE",
            "country":                    _s(r.get("CountryName")),
            "iso":                        _s(r.get("CountryCode")),
            "policy_description":         _s(r.get("InstrumentName_en")),
            "policydecision_details":     _s(r.get("InstrumentDescription")),
            "initialdate":                _s(eff_year),
            "y_start":                    eff_year,
            "policydirection":            _s(r.get("InstrumentType")),
            "instrument_type":            _s(r.get("InstrumentType")),
            "instrument_type_detail":     _s(r.get("InstrumentType_Detail")),
            "pine_status":                _s(r.get("Status")),
            "pine_domains":               _domains(r),
            # Compat columns with original FSPD PINE rows
            "generaltaxbase":             _s(r.get("InstrumentType")),
            "specifictaxbase":            _s(r.get("InstrumentType_Detail")),
            "url":                        _s(r.get("LinksOther")) if str(r.get("LinksOther","")).startswith("http") else None,
            "source1link":                _s(r.get("Reference_Details_1")),
            "source1name":                _s(r.get("Reference_Name_1")),
            "source2link":                _s(r.get("Reference_Details_2")),
            "source2name":                _s(r.get("Reference_Name_2")),
            "decision_making_institution": _s(r.get("Auth_Admin_National_Name")),
            "contextoradditionalinfo":    _s(r.get("Intervention")),
        })

    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} PINE rows after filter")
    return df


# ---------------------------------------------------------------------------
# Canonical schema (49 columns) — shared with update_dataset.py
# ---------------------------------------------------------------------------

CANONICAL_COLUMNS = [
    "id", "db", "country", "iso",
    "policy_description", "policydecision_details",
    "initialdate", "y_start", "y_end",
    "FAPDA_region", "FAPDA_subregion", "who_region",
    "policydirection", "policyphase",
    "targeted", "emergency", "term",
    "contextoradditionalinfo", "decision_making_institution",
    "budget", "beneficiaries",
    "policycategorycode", "policycategory",
    "sdg_codes", "roadmap_codes", "g20_codes", "quipd",
    "gendermainstreamed", "nutritionmainstreamed",
    "foodsecuritydimension",
    "commodity1", "commodity2", "commodity3", "additionalcommodities",
    "source1name", "source1link",
    "source2name", "source2link",
    "source3name", "source3link",
    "url", "topics",
    # GIFNA-specific
    "policy_type",
    # PINE-specific
    "instrument_type", "instrument_type_detail",
    "pine_status", "pine_domains",
    "generaltaxbase", "specifictaxbase",
]


# ---------------------------------------------------------------------------
# ISO lookup from frameworks (FAPDA decisions lack ISO codes)
# ---------------------------------------------------------------------------

def build_iso_lookup(fw_df: pd.DataFrame) -> dict[str, str]:
    """Country name → ISO3 from frameworks (which have both)."""
    pairs = fw_df[["country", "iso"]].dropna()
    lookup: dict[str, str] = {}
    for _, row in pairs.iterrows():
        c = str(row["country"]).strip()
        iso = str(row["iso"]).strip()
        if c and iso:
            lookup[c] = iso
    return lookup


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build(
    fapda_decisions: Path,
    fapda_frameworks: Path,
    gifna: Path,
    pine: Path,
    output: Path,
    also_csv: bool,
) -> pd.DataFrame:

    fw_df   = load_fapda_frameworks(fapda_frameworks)
    dec_df  = load_fapda_decisions(fapda_decisions)
    gif_df  = load_gifna(gifna)
    pine_df = load_pine(pine)

    # Fill ISO codes for decisions from frameworks lookup
    iso_lookup = build_iso_lookup(fw_df)
    dec_df["iso"] = dec_df["country"].map(iso_lookup)
    missing_iso = dec_df["iso"].isna().sum()
    if missing_iso:
        print(f"  FAPDA decisions: {missing_iso:,} rows with no ISO match (country name variants)")

    df = pd.concat([dec_df, fw_df, gif_df, pine_df], ignore_index=True, sort=False)

    # Normalise numeric cols that might be mixed type
    for col in ("gendermainstreamed", "nutritionmainstreamed", "y_start", "y_end"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    extra = [c for c in df.columns if c not in CANONICAL_COLUMNS]
    df = df[[c for c in CANONICAL_COLUMNS if c in df.columns] + extra]

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)
    print(f"\nWrote {len(df):,} rows → {output}")

    if also_csv:
        csv_path = output.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        print(f"Wrote CSV  → {csv_path}")

    # Summary
    print("\n=== Source breakdown ===")
    print(df["db"].value_counts().to_string())
    print("\n=== Coverage (% non-null) of key columns ===")
    key_cols = ["iso", "policy_description", "policydecision_details",
                "y_start", "policydirection", "policycategory", "url"]
    cov = df[[c for c in key_cols if c in df.columns]].notna().mean().mul(100).round(1)
    print(cov.to_string())

    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build FSPD canonical dataset from original source files.")
    parser.add_argument("--fapda_decisions",   type=Path,
                        default=REPO / "data/fapda/original/fapda_details-202605161452.xls")
    parser.add_argument("--fapda_frameworks",  type=Path,
                        default=REPO / "data/fapda/original/fapda_details-202605161451.xlsx")
    parser.add_argument("--gifna",             type=Path,
                        default=REPO / "data/gifna/original/GIFNA-SearchPage-policies-data-items-2026-05-16.csv")
    parser.add_argument("--pine",              type=Path,
                        default=REPO / "data/pine/original/OECD-PINEVersion2026.csv")
    parser.add_argument("--output",            type=Path,
                        default=REPO / "data/FSPD_new.parquet")
    parser.add_argument("--also_csv",          action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(
        fapda_decisions=args.fapda_decisions,
        fapda_frameworks=args.fapda_frameworks,
        gifna=args.gifna,
        pine=args.pine,
        output=args.output,
        also_csv=args.also_csv,
    )
