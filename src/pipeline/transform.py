"""
Transform raw JSONL files from FAPDA into the canonical FSPD schema, enrich with
GIFNA WHO boundaries, and carry forward Nourishing/PINE rows from the existing CSV.

Source coverage:
  FAPDA decisions  — freshly transformed from data/fapda/fapda_policy_decisions.jsonl
  FAPDA frameworks — freshly transformed from data/fapda/fapda_policy_frameworks.jsonl
  Nourishing       — carried forward from existing_labels (no individual-record ETL yet)
  PINE             — carried forward from existing_labels (PINE ETL fetches OECD SDMX
                     aggregates, not individual tax-instrument records)

ML labels (segment, lever, inclusion, envitarget, diethealth, taxonomy, defn, itype)
are inherited from the existing FSPD.csv where IDs match; new records get NaN.

Usage:
    python src/pipeline/transform.py
    python src/pipeline/transform.py --fapda_decisions data/fapda/fapda_policy_decisions.jsonl \
        --fapda_frameworks data/fapda/fapda_policy_frameworks.jsonl \
        --existing_labels data/FSPD.csv \
        --output data/FSPD_v2.parquet
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _parse_year(date_str: str | None) -> int | None:
    """Extract a 4-digit year from various date string formats."""
    if not date_str:
        return None
    # DD/MM/YYYY
    m = re.search(r"\b(\d{4})\b", str(date_str))
    return int(m.group(1)) if m else None


def _strip_write_permission(obj: Any) -> Any:
    """Recursively remove writePermission keys (API auth noise)."""
    if isinstance(obj, dict):
        return {k: _strip_write_permission(v) for k, v in obj.items() if k != "writePermission"}
    if isinstance(obj, list):
        return [_strip_write_permission(i) for i in obj]
    return obj


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _obj_desc(obj: Any, fallback_key: str = "description") -> str | None:
    """Extract english description from a nested FAPDA object."""
    if not isinstance(obj, dict):
        return None
    return _str(obj.get("description_en") or obj.get("description"))


def _pipe_join(items: list[str | None]) -> str | None:
    clean = [s for s in items if s]
    return "|".join(clean) if clean else None


# ---------------------------------------------------------------------------
# FAPDA decisions
# ---------------------------------------------------------------------------

def _source_link(src: dict[str, Any]) -> str | None:
    """Best URL from a source object: prefer external URL attachments, then attachmentLink."""
    if not isinstance(src, dict):
        return None
    # attachments list: fileType=1 means URL
    for att in src.get("attachments") or []:
        if isinstance(att, dict) and att.get("fileType") == 1 and att.get("filePath"):
            return _str(att["filePath"])
    # any attachment path
    for att in src.get("attachments") or []:
        if isinstance(att, dict) and att.get("filePath"):
            return _str(att["filePath"])
    return None


def transform_decision(rec: dict[str, Any]) -> dict[str, Any]:
    rec = _strip_write_permission(rec)
    row: dict[str, Any] = {}

    row["id"] = _str(rec.get("id"))
    row["db"] = "FAPDA"
    row["country"] = _str(rec.get("countryName"))
    row["iso"] = _str(rec.get("iso3"))
    row["policy_description"] = _str(rec.get("title"))
    row["policydecision_details"] = _str(rec.get("policyDetails") or rec.get("formattedDetails"))

    init_str = _str(rec.get("initialDateAsString"))
    row["initialdate"] = init_str
    row["y_start"] = _parse_year(init_str)
    end_str = _str(rec.get("endDateAsString"))
    row["y_end"] = _parse_year(end_str)

    pd_obj = rec.get("policyDirection") or {}
    row["policydirection"] = _obj_desc(pd_obj)
    row["policyphase"] = _str(rec.get("announcementImplementation"))
    row["targeted"] = _str(rec.get("targeted"))
    row["emergency"] = _str(rec.get("emergency"))
    row["term"] = _str(rec.get("termDescription"))
    row["contextoradditionalinfo"] = _str(rec.get("contextOrInfo"))
    row["decision_making_institution"] = _str(rec.get("decisionMakingInstitution"))
    row["budget"] = _str(rec.get("budget"))
    row["beneficiaries"] = _str(rec.get("beneficiary"))

    # Geolocation (new — not in original FSPD.csv)
    row["latitude"] = _safe_float(rec.get("latitude"))
    row["longitude"] = _safe_float(rec.get("longitude"))

    # GIEWS monitoring flag (new)
    giews = rec.get("giews")
    row["giews"] = bool(giews) if giews is not None else None

    # Policy measures: codes, food security dimension, DAC/CRS
    measures = rec.get("policyMeasures") or []
    if measures:
        codes = [_str(m.get("code")) for m in measures if m.get("code")]
        row["policycategorycode"] = _pipe_join(codes)
        crumbs = rec.get("policyMeasureCrumb") or []
        row["policyMeasureCrumb"] = " | ".join(crumbs) if crumbs else None
        row["foodsecuritydimension"] = next(
            (_obj_desc(m.get("foodSecDimension")) for m in measures if m.get("foodSecDimension")),
            None,
        )
        dac = [str(m["dacCode"]) for m in measures if m.get("dacCode")]
        crs = [str(m["crsCode"]) for m in measures if m.get("crsCode")]
        row["dac_codes"] = _pipe_join(dac)
        row["crs_codes"] = _pipe_join(crs)
    else:
        row["policycategorycode"] = None
        row["policyMeasureCrumb"] = None
        row["foodsecuritydimension"] = None
        row["dac_codes"] = None
        row["crs_codes"] = None

    # Commodities
    comms = [_obj_desc(c) for c in (rec.get("commodities") or []) if isinstance(c, dict)]
    comms = [c for c in comms if c]
    row["commodity1"] = comms[0] if len(comms) > 0 else None
    row["commodity2"] = comms[1] if len(comms) > 1 else None
    row["commodity3"] = comms[2] if len(comms) > 2 else None
    row["additionalcommodities"] = "; ".join(comms[3:]) if len(comms) > 3 else None

    # Sources (up to 3)
    sources = [s for s in (rec.get("sources") or []) if isinstance(s, dict)]
    for i, src in enumerate(sources[:3], 1):
        row[f"source{i}name"] = _obj_desc(src)
        row[f"source{i}link"] = _source_link(src)
    for i in range(len(sources[:3]) + 1, 4):
        row[f"source{i}name"] = None
        row[f"source{i}link"] = None

    row["url"] = f"http://fapda.apps.fao.org/fapda/index.html#main.html?policydecisionid={rec['id']}"

    # G20 / topics
    g20s = [_obj_desc(g) for g in (rec.get("policyDecisionG20s") or []) if isinstance(g, dict)]
    row["topics"] = "; ".join(g for g in g20s if g) or None

    row["yearoflastrevision"] = _str(rec.get("lastEditDateAsString"))
    row["framework"] = _str(rec.get("customGroupCountryId"))  # link to parent framework if any

    return row


# ---------------------------------------------------------------------------
# FAPDA frameworks
# ---------------------------------------------------------------------------

def transform_framework(rec: dict[str, Any]) -> dict[str, Any]:
    rec = _strip_write_permission(rec)
    row: dict[str, Any] = {}

    row["id"] = _str(rec.get("id"))
    row["db"] = "FAPDA_F"

    country_obj = rec.get("country") or {}
    row["country"] = _str(country_obj.get("description") if isinstance(country_obj, dict) else rec.get("countryName"))
    row["iso"] = _str(country_obj.get("iso3") if isinstance(country_obj, dict) else rec.get("iso3"))

    row["policy_description"] = _str(rec.get("title"))
    row["policydecision_details"] = _str(rec.get("description"))
    row["contextoradditionalinfo"] = _str(rec.get("additionalInformation") or rec.get("cppDescription"))

    # Framework type maps to policydirection (Policy, Strategy, Plan, Law, …)
    fw_type = rec.get("policyFrameworkType") or {}
    row["policydirection"] = _obj_desc(fw_type)

    row["decision_making_institution"] = _obj_desc(rec.get("source"))

    # Dates — frameworks use fromYear / toYear integers, plus adoptionDate string
    from_year = rec.get("fromYear")
    to_year = rec.get("toYear")
    adoption = _str(rec.get("adoptionDate"))
    row["initialdate"] = adoption
    row["y_start"] = int(from_year) if from_year else _parse_year(adoption)
    row["y_end"] = int(to_year) if to_year else None

    # Source / attachment
    att = rec.get("attachment") or {}
    att_link = _str(rec.get("attachmentLink") or rec.get("policyDocumentLink"))
    row["source1name"] = _str(att.get("name")) if isinstance(att, dict) else None
    row["source1link"] = att_link
    row["source2name"] = None
    row["source2link"] = None
    row["source3name"] = None
    row["source3link"] = None

    row["url"] = f"http://fapda.apps.fao.org/fapda/index.html#main.html?policyframeworkid={rec['id']}"

    # Classification codes
    classifications = rec.get("policyFrameworkClassifications") or []
    cls_ids = [_str(c.get("id")) for c in classifications if isinstance(c, dict) and c.get("id")]
    cls_labels = [_obj_desc(c) for c in classifications if isinstance(c, dict)]
    row["policycategorycode"] = _pipe_join(cls_ids)
    row["policyFrameworkCrumb"] = " | ".join(l for l in cls_labels if l) or None

    # SDG codes (new — frameworks only)
    sdgs = rec.get("policyFrameworkSdgs") or []
    sdg_codes = [_str(s.get("code")) for s in sdgs if isinstance(s, dict) and s.get("code")]
    row["sdg_codes"] = _pipe_join(sdg_codes)

    # Roadmap codes (new)
    roadmaps = rec.get("policyFrameworkRoadmaps") or []
    rm_codes = [_str(r.get("code")) for r in roadmaps if isinstance(r, dict) and r.get("code")]
    row["roadmap_codes"] = _pipe_join(rm_codes)

    # G20 topics
    g20s = [_obj_desc(g) for g in (rec.get("policyFrameworkG20s") or []) if isinstance(g, dict)]
    row["topics"] = "; ".join(g for g in g20s if g) or None

    # Mainstreaming flags
    row["gendermainstreamed"] = rec.get("genderMainstreamed")
    row["nutritionmainstreamed"] = rec.get("nutritionMainstreamed")

    # Score
    row["pqi_score"] = rec.get("pqiScore")

    row["framework"] = row["id"]  # for frameworks, framework = self
    row["yearoflastrevision"] = _str(rec.get("lastModifiedDate"))

    return row


# ---------------------------------------------------------------------------
# Lookups built from existing FSPD.csv and GIFNA boundaries
# ---------------------------------------------------------------------------

def build_country_lookup(existing_df: pd.DataFrame) -> pd.DataFrame:
    """Per-ISO enrichment: income_group, region_wb, fsd_group, FAPDA regions, EU flags."""
    enrich_cols = [
        "iso", "income_group", "region_wb", "fsd_group",
        "FAPDA_region", "FAPDA_subregion",
        "is_eu_country", "is_eu_wide", "income_grp2",
    ]
    available = [c for c in enrich_cols if c in existing_df.columns]
    return (
        existing_df[available]
        .dropna(subset=["iso"])
        .drop_duplicates(subset=["iso"])
        .set_index("iso")
    )


def build_who_region_lookup(gifna_boundaries_path: Path | None) -> dict[str, str]:
    """ISO3 → WHO_REGION from GIFNA boundaries JSONL."""
    if not gifna_boundaries_path or not gifna_boundaries_path.exists():
        return {}
    records = _read_jsonl(gifna_boundaries_path)
    return {
        r["ISO_3_CODE"]: r["WHO_REGION"]
        for r in records
        if r.get("ISO_3_CODE") and r.get("WHO_REGION")
    }


def build_label_lookup(existing_df: pd.DataFrame) -> pd.DataFrame:
    """Per-ID ML labels + ancillary annotation columns."""
    label_cols = [
        "id", "segment", "lever",
        "inclusion", "envitarget", "diethealth",
        "taxonomy", "defn", "itype",
        "covid_mentioned", "level",
    ]
    available = [c for c in label_cols if c in existing_df.columns]
    return (
        existing_df[available]
        .dropna(subset=["id"])
        .drop_duplicates(subset=["id"])
        .assign(id=lambda df: df["id"].astype(str))
        .set_index("id")
    )


# ---------------------------------------------------------------------------
# Main transform pipeline
# ---------------------------------------------------------------------------

# Columns to carry forward verbatim from existing CSV for pass-through sources
_PASSTHROUGH_COLS = [
    "id", "db", "country", "iso", "policy_description", "policydecision_details",
    "initialdate", "y_start", "y_end", "policydirection", "policyphase",
    "targeted", "emergency", "term", "contextoradditionalinfo",
    "decision_making_institution", "budget", "beneficiaries",
    "policycategorycode", "policyMeasureCrumb", "foodsecuritydimension",
    "commodity1", "commodity2", "commodity3", "additionalcommodities",
    "source1name", "source1link", "source2name", "source2link",
    "source3name", "source3link", "url", "topics", "yearoflastrevision",
    "framework", "policy_part", "gendermainstreamed", "nutritionmainstreamed",
    "FAPDA_region", "FAPDA_subregion",
    # source-specific
    "source", "generaltaxbase", "specifictaxbase", "rate",
    "exemptiontype", "exemptiondetails", "earmarking",
    # ML labels
    "segment", "lever", "inclusion", "envitarget", "diethealth",
    "taxonomy", "defn", "itype", "covid_mentioned", "level",
    # enrichment
    "income_group", "region_wb", "fsd_group",
    "is_eu_country", "is_eu_wide", "income_grp2",
]


def transform_all(
    fapda_decisions_path: Path | None,
    fapda_frameworks_path: Path | None,
    existing_labels_path: Path | None,
    gifna_boundaries_path: Path | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    if fapda_decisions_path and fapda_decisions_path.exists():
        records = _read_jsonl(fapda_decisions_path)
        print(f"Transforming {len(records):,} FAPDA decisions…")
        rows.extend(transform_decision(r) for r in records)

    if fapda_frameworks_path and fapda_frameworks_path.exists():
        records = _read_jsonl(fapda_frameworks_path)
        print(f"Transforming {len(records):,} FAPDA frameworks…")
        rows.extend(transform_framework(r) for r in records)

    if not rows:
        raise RuntimeError("No FAPDA source data found — check paths.")

    fapda_df = pd.DataFrame(rows)

    existing: pd.DataFrame | None = None
    if existing_labels_path and existing_labels_path.exists():
        existing = pd.read_csv(existing_labels_path, low_memory=False)
        existing["id"] = existing["id"].astype(str)

    # Carry forward Nourishing and PINE rows verbatim from existing CSV
    passthrough_parts: list[pd.DataFrame] = []
    if existing is not None:
        for db in ("Nourishing", "PINE"):
            pt = existing[existing["db"] == db].copy()
            if len(pt):
                avail = [c for c in _PASSTHROUGH_COLS if c in pt.columns]
                passthrough_parts.append(pt[avail])
                print(f"Carrying forward {len(pt):,} {db} rows from existing CSV.")

    # Enrich FAPDA rows: country metadata + ML labels
    if existing is not None:
        country_lookup = build_country_lookup(existing)
        label_lookup = build_label_lookup(existing)
        fapda_df = fapda_df.join(country_lookup, on="iso", how="left")
        fapda_df["id"] = fapda_df["id"].astype(str)
        fapda_df = fapda_df.join(label_lookup, on="id", how="left")
        print(
            f"Labels inherited for "
            f"{fapda_df['segment'].notna().sum():,}/{len(fapda_df):,} FAPDA rows "
            f"({fapda_df['segment'].notna().mean():.1%})"
        )

    # Add WHO region from GIFNA boundaries
    who_lookup = build_who_region_lookup(gifna_boundaries_path)
    if who_lookup:
        fapda_df["who_region"] = fapda_df["iso"].map(who_lookup)
        for pt in passthrough_parts:
            if "iso" in pt.columns:
                pt["who_region"] = pt["iso"].map(who_lookup)

    # Combine
    all_parts = [fapda_df] + passthrough_parts
    df = pd.concat(all_parts, ignore_index=True, sort=False)

    # Normalize mixed-type columns that pyarrow can't handle as object
    for col in ("framework", "policy_part", "gendermainstreamed", "nutritionmainstreamed",
                "pqi_score", "is_eu_country", "is_eu_wide"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Build canonical FSPD dataset from raw JSONL sources.")
    parser.add_argument("--fapda_decisions", type=Path, default=repo / "data/fapda/fapda_policy_decisions.jsonl")
    parser.add_argument("--fapda_frameworks", type=Path, default=repo / "data/fapda/fapda_policy_frameworks.jsonl")
    parser.add_argument("--existing_labels", type=Path, default=repo / "data/FSPD.csv",
                        help="Existing labelled dataset to inherit ML annotations and country enrichment from.")
    parser.add_argument("--gifna_boundaries", type=Path,
                        default=repo / "data/gifna/gifna_who_boundaries_records.jsonl",
                        help="GIFNA WHO boundaries JSONL for WHO region enrichment.")
    parser.add_argument("--output", type=Path, default=repo / "data/FSPD_v2.parquet")
    parser.add_argument("--also_csv", action="store_true", help="Also write a .csv alongside the parquet.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = transform_all(
        fapda_decisions_path=args.fapda_decisions,
        fapda_frameworks_path=args.fapda_frameworks,
        existing_labels_path=args.existing_labels,
        gifna_boundaries_path=args.gifna_boundaries,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.output, index=False)
    print(f"Wrote {len(df):,} rows → {args.output}")

    if args.also_csv:
        csv_path = args.output.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        print(f"Wrote CSV → {csv_path}")

    print("\nColumn summary:")
    print(df.dtypes.to_string())
    print(f"\nLabel coverage:\n{df[['segment','lever','inclusion','envitarget','diethealth']].notna().mean().to_string()}")


if __name__ == "__main__":
    main()
