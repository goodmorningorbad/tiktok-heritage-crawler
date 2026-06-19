#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply final audit-display corrections for TikTok closed tables.

Problem fixed:
- False-breakout projects were demoted in tier/quadrant, but their default
  `likely_total_play` still displayed row-level statistical likely play, causing
  Fu ship / abacus to look like valid 100M+ reach cases.
- Mongolian long song had manual-confirmed high-view relevant rows but remained
  described as near-invisible/noise-checked in the final findings table.

This script preserves statistical fields and adds explicit final/audit-adjusted
fields, then rewrites the final-display columns used by the closed bundle.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINDINGS_CSV = ROOT / "data/derived/tiktok_manual_corrected_final_project_findings_20260619.csv"
FINDINGS_JSON = ROOT / "data/derived/tiktok_manual_corrected_final_project_findings_20260619.json"
MATRIX_CSV = ROOT / "data/derived/project_stock_reach_matrix_manual_corrected.csv"
MATRIX_JSON = ROOT / "data/derived/project_stock_reach_matrix_manual_corrected.json"
REACH_CSV = ROOT / "data/derived/project_reach_manual_corrected.csv"
SUMMARY_JSON = ROOT / "data/derived/tiktok_final_audit_display_corrections_20260619.json"

FALSE_BREAKOUTS = {
    "中国水密隔舱福船制造技艺": {
        "note": "9/9 targeted high-impact manual samples were unrelated (junk journal/BTS/Jungkook collisions); those video-level noise rows are deducted, while remaining likely_relevant rows stay counted.",
    },
    "中国珠算": {
        "note": "9/9 targeted high-impact manual samples were unrelated (mental arithmetic/abacus/generic music/food collisions); those video-level noise rows are deducted, while remaining likely_relevant rows stay counted.",
    },
    "麦西热甫": {
        "note": "Targeted high-impact manual audit found sampled breakout evidence unrelated; those video-level noise rows are deducted, while remaining likely_relevant rows stay counted.",
    },
}

LONG_SONG = "蒙古族长调民歌"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def clean_cell(v: Any) -> Any:
    if isinstance(v, str):
        return v.rstrip()
    return v


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: clean_cell(row.get(k, "")) for k in fields})


def as_int(v: Any) -> int:
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def append_matrix_note_once(row: dict[str, Any], text: str) -> None:
    if "matrix_note" not in row:
        return
    cur = str(row.get("matrix_note") or "")
    # Make this correction script idempotent across reruns.
    for stale in [
        "; final_likely_total_play=0 after false-breakout audit",
        "; high-impact noise rows deducted only; remaining likely_relevant reach retained",
        "; manual audit confirms high-noise niche reach for long song",
    ]:
        while stale in cur:
            cur = cur.replace(stale, "")
    row["matrix_note"] = cur + "; " + text


def add_after(fields: list[str], after: str, additions: list[str]) -> list[str]:
    out = list(fields)
    for a in additions:
        if a in out:
            out.remove(a)
    idx = out.index(after) + 1 if after in out else len(out)
    for i, a in enumerate(additions):
        out.insert(idx + i, a)
    return out


def long_song_manual_confirmed_play() -> int:
    # Use the final row-label table because it already includes duplicated baseline
    # rows and manual overrides consistently with project_reach_manual_corrected.
    total = 0
    reviewed_related = 0
    import json as _json
    p = ROOT / "data/derived/video_relevance_labels_manual_corrected.ndjson"
    with p.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = _json.loads(line)
            if d.get("project_name") == LONG_SONG and d.get("manual_review_applied") and d.get("quality_label") == "likely_relevant":
                total += as_int(d.get("stats_play_count"))
                reviewed_related += 1
    if total == 0:
        raise SystemExit("could not compute long-song manual-confirmed play")
    return total


def patch_common(row: dict[str, Any], table: str, long_song_play: int) -> dict[str, Any]:
    name = row.get("project_name")
    statistical = as_int(row.get("statistical_likely_total_play") or row.get("likely_total_play"))
    row["statistical_likely_total_play"] = statistical
    row.setdefault("audit_adjusted_note", "")
    row.setdefault("final_likely_total_play", statistical)
    row.setdefault("final_reach_display_note", "statistical row-level likely play; no additional project-level audit adjustment")

    if name in FALSE_BREAKOUTS:
        # Targeted audit only invalidates the manually reviewed high-impact noise
        # videos. Those rows have already been relabeled at video level, so the
        # remaining unreviewed `likely_relevant` rows still count as machine-
        # likely reach. Do not collapse the whole project to zero.
        row["final_likely_total_play"] = statistical
        row["likely_total_play"] = statistical
        row["audit_adjusted_likely_total_play"] = statistical
        row["final_reach_display_note"] = "video-level correction only: manually confirmed noise rows deducted; remaining likely_relevant videos retained"
        row["audit_adjusted_note"] = FALSE_BREAKOUTS[name]["note"]
        row["manual_audit_verdict"] = "false_breakout_confirmed"
        if "manual_audit_note" in row:
            row["manual_audit_note"] = FALSE_BREAKOUTS[name]["note"]
        if "likely_reach_tier_final" in row:
            row["likely_reach_tier_final"] = row.get("likely_reach_tier_statistical") or row.get("likely_reach_tier_final")
        if "likely_reach_tier" in row:
            row["likely_reach_tier"] = row.get("likely_reach_tier_statistical") or row.get("likely_reach_tier")
        if "reach_band" in row:
            row["reach_band"] = row.get("reach_band_statistical") or row.get("reach_band")
        row["quadrant"] = row.get("previous_quadrant") or ("stock_low__reach_high" if row.get("stock_band") != "stock_high" and row.get("reach_band") == "reach_high" else ("stock_low__reach_low" if row.get("stock_band") != "stock_high" else ("stock_high__reach_high" if row.get("reach_band") == "reach_high" else "stock_high__reach_low")))
        if row["quadrant"] == "stock_low__reach_high":
            row["quadrant_label"] = "低存量高触达：小而精破圈候选"
        elif row["quadrant"] == "stock_high__reach_high":
            row["quadrant_label"] = "真·规模化出海候选"
        elif row["quadrant"] == "stock_high__reach_low":
            row["quadrant_label"] = "高存量低触达：自产自销/虚假繁荣候选"
        else:
            row["quadrant_label"] = "低存量低触达：近乎隐形候选"
        if "final_tier" in row and str(row.get("final_tier") or "") == "T0_false_breakout_demoted":
            row["final_tier"] = "T2_small_breakout" if row.get("quadrant") == "stock_low__reach_high" else row.get("final_tier")
        if "headline_claim" in row:
            row["headline_claim"] = f"{name} 的已核查高播放 breakout 噪声已逐条扣除；剩余未被人工推翻的 likely_relevant 视频仍计入最终触达。"
        if "interpretation" in row:
            row["interpretation"] = "人工核查否定的是抽中的高影响噪声视频，不是整个项目归零；最终口径为逐条扣除已确认噪声，保留剩余机器 likely 相关触达。"
        append_matrix_note_once(row, "high-impact noise rows deducted only; remaining likely_relevant reach retained")
        return row

    if name == LONG_SONG:
        # This project is noisy, but not invisible: manual review confirmed three
        # relevant high-play throat-singing/Mongolian music rows in the row-label table.
        row["final_likely_total_play"] = long_song_play
        row["likely_total_play"] = long_song_play
        row["audit_adjusted_likely_total_play"] = long_song_play
        row["final_reach_display_note"] = "manual-confirmed relevant high-view rows retained; noisy unrelated long-song/music collisions remain documented"
        row["audit_adjusted_note"] = "Manual review found 3 relevant high-play Mongolian throat-singing/music rows and 10 unrelated/noisy rows; final narrative is high-noise confirmed niche reach, not near-invisible."
        if "final_tier" in row:
            row["final_tier"] = "T2_small_breakout"
        if "likely_reach_tier_final" in row:
            row["likely_reach_tier_final"] = "manual_confirmed_high_noise_niche_reach"
        if "likely_reach_tier" in row:
            row["likely_reach_tier"] = "manual_confirmed_high_noise_niche_reach"
        if "reach_band" in row:
            row["reach_band"] = "reach_high"
        if "quadrant" in row:
            row["quadrant"] = "stock_low__reach_high"
        if "quadrant_label" in row:
            row["quadrant_label"] = "人工确认高噪声小众破圈"
        if "review_priority" in row:
            row["review_priority"] = "P1_manual_confirmed_high_noise_niche"
        if "headline_claim" in row:
            row["headline_claim"] = "蒙古族长调民歌 经人工核查确认存在高播放相关触达，但噪声与边界风险高，应作为高噪声小众破圈案例。"
        if "interpretation" in row:
            row["interpretation"] = "人工核查并未否定全部高触达：3 条相关高播放样本支撑小众破圈；同时 10 条不相关样本说明关键词噪声很高，结论须谨慎表达。"
        append_matrix_note_once(row, "manual audit confirms high-noise niche reach for long song")
        return row

    row["audit_adjusted_likely_total_play"] = row.get("audit_adjusted_likely_total_play", statistical)
    return row


def patch_table(csv_path: Path, json_path: Path | None, table: str, long_song_play: int) -> list[dict[str, Any]]:
    fields, rows = read_csv(csv_path)
    new_fields = add_after(fields, "likely_total_play", [
        "statistical_likely_total_play",
        "final_likely_total_play",
        "audit_adjusted_likely_total_play",
        "final_reach_display_note",
        "audit_adjusted_note",
    ])
    patched = [patch_common(dict(r), table, long_song_play) for r in rows]
    write_csv(csv_path, new_fields, patched)
    if json_path:
        json_path.write_text(json.dumps(patched, ensure_ascii=False, indent=2), encoding="utf-8")
    return patched


def main() -> int:
    long_song_play = long_song_manual_confirmed_play()
    findings = patch_table(FINDINGS_CSV, FINDINGS_JSON, "findings", long_song_play)
    matrix = patch_table(MATRIX_CSV, MATRIX_JSON, "matrix", long_song_play)
    # Do not rewrite project_reach_manual_corrected: it is deliberately row-level
    # statistical aggregation. The final display corrections live in findings/matrix.
    summary = {
        "long_song_manual_confirmed_likely_play": long_song_play,
        "false_breakout_final_likely_total_play": {
            name: as_int(next((r.get("statistical_likely_total_play") or r.get("likely_total_play") for r in findings if r.get("project_name") == name), 0))
            for name in FALSE_BREAKOUTS
        },
        "changed_projects": ["中国水密隔舱福船制造技艺", "中国珠算", "麦西热甫", LONG_SONG],
        "note": "false-breakout audit now deducts only manually confirmed noise videos; remaining likely_relevant reach is retained. project_reach remains statistical row-level aggregation.",
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
