"""
Render the monthly-update run report (PR body / job summary) as Markdown.

Inputs: the JSON summary from update_dataset.py, optionally the classified
new-rows parquet from classify_new.py, the per-source fetch step outcomes
from the GitHub Actions fetch job, and the run URL.

Pure pandas/stdlib — no ML imports.

Usage (in CI):
    python -m src.pipeline.make_pr_body \
        --summary data/updates/summary_<YYYYMMDD>.json \
        --classified data/updates/new_rows_<YYYYMMDD>_classified.parquet \
        --fapda_status success --pine_status failure --gifna_status success \
        --run_url https://github.com/ncerutti/FSPD/actions/runs/123 \
        --output pr_body.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

STATUS_LABEL = {
    "success": "OK",
    "failure": "FAILED",
    "skipped": "skipped",
    "cancelled": "cancelled",
    "": "unknown",
}


def _fetch_section(args: argparse.Namespace) -> list[str]:
    lines = ["## Fetch", "", "| Source | Status |", "|---|---|"]
    for name, status in (("FAPDA", args.fapda_status),
                         ("PINE", args.pine_status),
                         ("GIFNA (freshness signal)", args.gifna_status)):
        lines.append(f"| {name} | {STATUS_LABEL.get(status, status)} |")
    lines.append("")
    if args.pine_status == "failure":
        lines += [
            "> **WARNING: the PINE fetch FAILED.** No PINE rows were processed this run. "
            "The OECD Shiny app may have been redeployed — see the failure playbook in "
            "`docs/automation.md` and the fragility note in `docs/fetching.md`.",
            "",
        ]
    if args.gifna_status == "failure":
        lines += [
            "> Note: the GIFNA freshness-signal fetch failed; the GIFNA staleness "
            "check below is unavailable this run.",
            "",
        ]
    return lines


def _sources_section(summary: dict) -> list[str]:
    lines = ["## New rows by source", "",
             "| Source | Fetched | Duplicates (in batch) | Already in dataset | New |",
             "|---|---|---|---|---|"]
    for db, info in summary.get("sources", {}).items():
        if "skipped" in info:
            lines.append(f"| {db} | skipped: {info['skipped']} | — | — | — |")
        else:
            lines.append(
                f"| {db} | {info['fetched']:,} | {info['within_batch_duplicates']:,} "
                f"| {info['already_in_dataset']:,} | **{info['new']:,}** |"
            )
    lines += [
        "",
        f"Dataset: {summary['existing_rows']:,} rows -> {summary['output_rows']:,} rows "
        f"(+{summary['new_rows_total']:,}).",
        "",
    ]
    return lines


def _classification_section(classified: Path | None, new_rows_total: int) -> list[str]:
    lines = ["## Classification", ""]
    if new_rows_total == 0:
        lines += ["No new rows this run — classification skipped.", ""]
        return lines
    if classified is None or not classified.exists():
        lines += ["Classified file not found — classification did not run.", ""]
        return lines
    import pandas as pd  # deferred so the zero-new-rows path needs no pandas

    df = pd.read_parquet(classified)
    n = len(df)
    n_review = int(df["needs_review"].sum()) if "needs_review" in df.columns else 0
    lines += [
        f"- Rows classified: **{n:,}**",
        f"- Flagged `needs_review` (any task confidence < 0.7): **{n_review:,}** "
        f"({100 * n_review / max(n, 1):.1f}%)",
    ]
    conf_cols = sorted(c for c in df.columns if c.endswith("_confidence"))
    if conf_cols:
        lines += ["", "| Task | Mean confidence | < 0.7 |", "|---|---|---|"]
        for col in conf_cols:
            task = col.removesuffix("_confidence")
            lines.append(f"| {task} | {df[col].mean():.3f} | {int((df[col] < 0.7).sum()):,} |")
    lines.append("")
    return lines


def _gifna_section(summary: dict) -> list[str]:
    fresh = summary.get("gifna_freshness") or {}
    lines = ["## GIFNA freshness", ""]
    if fresh.get("refresh_recommended"):
        lines += [
            "> **ACTION NEEDED: GIFNA manual refresh recommended.** "
            f"Map action total {fresh.get('map_action_total'):,} exceeds the expected "
            f"{fresh.get('expected_actions_at_current_rows'):,} for the current "
            f"{fresh.get('dataset_gifna_rows'):,} GIFNA rows. Follow the manual export "
            "procedure in `docs/pipeline.md` (GIFNA manual refresh).",
        ]
    elif fresh.get("refresh_recommended") is False:
        lines.append(
            f"No refresh needed: map action total {fresh.get('map_action_total'):,}, "
            f"dataset GIFNA rows {fresh.get('dataset_gifna_rows'):,}."
        )
    else:
        lines.append(f"Freshness signal unavailable: {fresh.get('note')}")
    lines.append("")
    return lines


def build_body(args: argparse.Namespace) -> str:
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    lines = [f"# OpenFPD monthly data update — {summary.get('run_date', 'unknown date')}", ""]
    lines += _fetch_section(args)
    lines += _sources_section(summary)
    lines += _classification_section(
        Path(args.classified) if args.classified else None,
        int(summary.get("new_rows_total", 0)),
    )
    lines += _gifna_section(summary)
    if args.run_url:
        lines += [f"Workflow run: {args.run_url}", ""]
    lines += ["Generated automatically by `.github/workflows/monthly-update.yml`.", ""]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the monthly-update PR body.")
    parser.add_argument("--summary", required=True, help="JSON summary from update_dataset.py")
    parser.add_argument("--classified", default=None,
                        help="Classified new-rows parquet (omit when no rows were classified)")
    parser.add_argument("--fapda_status", default="")
    parser.add_argument("--pine_status", default="")
    parser.add_argument("--gifna_status", default="")
    parser.add_argument("--run_url", default="")
    parser.add_argument("--output", required=True, help="Markdown output path")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    body = build_body(args)
    Path(args.output).write_text(body, encoding="utf-8")
    print(f"Wrote {args.output} ({len(body)} chars)")
