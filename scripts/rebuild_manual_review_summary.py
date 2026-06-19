#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild full manual review summary from current applied artifacts."""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "data/derived/manual_review_returned_20260619.csv"
APPLIED = ROOT / "data/derived/manual_review_returned_applied.csv"
LABELS = ROOT / "data/derived/video_relevance_labels_manual_corrected.ndjson"
OUT = ROOT / "data/derived/manual_review_returned_summary.json"
FINAL_OUT = ROOT / "data/final/tiktok_closed_20260619/manual_review/manual_review_summary.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    manual = read_csv(MANUAL)
    applied = read_csv(APPLIED)
    manual_valid_urls = {(r.get("video_url") or r.get("web_url") or "").strip() for r in manual if (r.get("manual_relevance") or r.get("manual_label") or "").strip()}
    applied_urls = {(r.get("web_url") or r.get("video_url") or "").strip() for r in applied}
    unmatched = sorted(u for u in manual_valid_urls - applied_urls if u)

    row_label_manual = 0
    row_label_counts = Counter()
    with LABELS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("manual_review_applied"):
                row_label_manual += 1
                row_label_counts[d.get("quality_label") or ""] += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manual_rows": len(manual),
        "manual_urls_with_valid_label": len(manual_valid_urls),
        "manual_label_counts_raw": dict(Counter((r.get("manual_relevance") or r.get("manual_label") or "").strip() for r in manual)),
        "manual_matched_urls": len(manual_valid_urls - set(unmatched)),
        "manual_unmatched_urls": len(unmatched),
        "unmatched_urls": unmatched,
        "manual_applied_rows": len(applied),
        "manual_changed_rows": sum(1 for r in applied if str(r.get("label_changed")) == "True"),
        "manual_unchanged_rows": sum(1 for r in applied if str(r.get("label_changed")) != "True"),
        "applied_label_counts": dict(Counter(r.get("manual_label") or "" for r in applied)),
        "row_labels_manual_review_applied_rows": row_label_manual,
        "row_labels_manual_quality_label_counts": dict(row_label_counts),
        "manual_related_rows": row_label_counts.get("likely_relevant", 0),
        "manual_uncertain_rows": row_label_counts.get("needs_review", 0),
        "manual_unrelated_rows": row_label_counts.get("low_relevance", 0),
        "note": "manual_relevance overrides quality_label only for reviewed rows; unreviewed labels remain automatic. One manual row with malformed/placeholder URL did not match baseline.",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    FINAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    FINAL_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
