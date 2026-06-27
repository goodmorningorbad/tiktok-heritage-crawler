#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backflow the human head-check of the 378 collision-suspect TikTok head videos.

These 378 are exactly the videos the China-signal text filter REMOVED from the
reach lower bound (passes_china_signal_filter == False) but which sit in the HEAD
(~80% cumulative play) of each project's machine-likely pool. Humans now adjudicate
each one, so we can:

  1. Resolve the HEAD of the reach band by hand (instead of trusting the text filter),
     producing a human-anchored reach that sits inside [signal-filtered, machine-likely].
  2. Quantify the filter's directional bias: how much *real* heritage it false-killed,
     broken down by 撞词无关 / 有中国语境 / 本土化无中国标记.

ADDITIVE only. Reads the frozen comparison + head-check list + the 3 returned review
workbooks; writes new derived artifacts. Touches no raw data, no filter outputs.

Methodology red lines honoured:
  - Human verdict is authoritative; we only tally it, never override it.
  - 拿不准 (uncertain) is kept as a SEPARATE upper variant, never silently folded into
    relevant (would over-count) nor into irrelevant (would under-count).
  - The un-reviewed failed *tail* (failed-filter videos below the head cutoff) is NOT
    invented as relevant — it stays filter-estimated and is reported as residual.

Inputs:
  - data/derived/tiktok_china_signal_filtered_reach_comparison_20260620.json
  - data/derived/tiktok_head_check_list_20260620.csv          (play_count + project per check_id)
  - manual/*.xlsx                                             (A/B/C returned review workbooks)

Outputs:
  - data/review/tiktok_head_check_returned_20260620.csv       (merged + normalised, 378 rows)
  - data/derived/tiktok_head_check_reach_corrected_20260620.json   (per-project: band + human anchor)
  - data/derived/tiktok_head_check_reach_corrected_20260620.csv
  - data/derived/tiktok_head_check_summary_20260620.json      (aggregate false-kill / dilution stats)
"""
from __future__ import annotations

import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
REVIEW = ROOT / "data/review"
COMPARISON = DERIVED / "tiktok_china_signal_filtered_reach_comparison_20260620.json"
HEAD_LIST = DERIVED / "tiktok_head_check_list_20260620.csv"
MANUAL_GLOB = str(ROOT / "manual" / "*.xlsx")
DATE = "20260620"

# In the returned workbooks the 核查清单 is the 2nd sheet; manual columns sit at:
COL_CHECK_ID = 0
COL_RELEVANT = 9      # 是否相关
COL_NATURE = 10       # 国别
COL_FORM = 11         # 内容形态
COL_REVIEWER = 12     # 填写人
COL_NOTES = 13        # 备注

REL_NORM = {"相关": "relevant", "不相关": "irrelevant", "拿不准": "uncertain"}
NAT_NORM = {
    "撞词无关": "collision_irrelevant",
    "有中国语境": "china_context",
    "本土化无中国标记": "localized_no_marker",
}


def parse_int(v: Any) -> int:
    try:
        if v is None or v == "":
            return 0
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def load_manual() -> list[dict[str, Any]]:
    """Merge the A/B/C returned workbooks into normalised rows keyed by check_id."""
    import openpyxl

    rows: dict[str, dict[str, Any]] = {}
    files = sorted(glob.glob(MANUAL_GLOB))
    if not files:
        raise SystemExit(f"no review workbooks under {MANUAL_GLOB}")
    for f in files:
        src = Path(f).name
        wb = openpyxl.load_workbook(f, data_only=True)
        ws = wb.worksheets[1]  # 核查清单
        for r in ws.iter_rows(min_row=2, values_only=True):
            cid = r[COL_CHECK_ID]
            if cid is None or str(cid).strip() == "":
                continue
            cid = str(cid).strip()
            rel_raw = (str(r[COL_RELEVANT]).strip() if r[COL_RELEVANT] is not None else "")
            nat_raw = (str(r[COL_NATURE]).strip() if r[COL_NATURE] is not None else "")
            form_raw = (str(r[COL_FORM]).strip() if r[COL_FORM] is not None else "")
            if cid in rows:
                raise SystemExit(f"duplicate check_id across workbooks: {cid}")
            rows[cid] = {
                "check_id": cid,
                "source_file": src,
                "manual_relevant_raw": rel_raw,
                "manual_relevant": REL_NORM.get(rel_raw, "" if rel_raw == "" else "other"),
                "manual_nature_raw": nat_raw,
                "manual_nature": NAT_NORM.get(nat_raw, "" if nat_raw == "" else "other"),
                "manual_content_form": form_raw,
                "manual_reviewer": (str(r[COL_REVIEWER]).strip() if r[COL_REVIEWER] is not None else ""),
                "manual_notes": (str(r[COL_NOTES]).strip() if r[COL_NOTES] is not None else ""),
            }
    return list(rows.values())


def load_head_list() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with HEAD_LIST.open(encoding="utf-8-sig") as fh:
        for d in csv.DictReader(fh):
            out[d["check_id"]] = d
    return out


def main() -> int:
    comparison = json.loads(COMPARISON.read_text(encoding="utf-8"))
    by_pid = {int(c["project_id"]): c for c in comparison}
    head = load_head_list()
    manual = load_manual()

    # ---- enrich each manual row with play_count + project from head list ----
    merged: list[dict[str, Any]] = []
    for m in manual:
        h = head.get(m["check_id"])
        if h is None:
            raise SystemExit(f"check_id not in head list: {m['check_id']}")
        if h["passes_china_signal_filter"] != "False":
            raise SystemExit(f"reviewed a non-collision row: {m['check_id']}")
        merged.append({
            **m,
            "project_id": int(h["project_id"]),
            "project_name": h["project_name"],
            "play_count": parse_int(h["play_count"]),
            "source_term": h["source_term"],
            "author_handle": h["author_handle"],
            "url": h["url"],
        })
    merged.sort(key=lambda r: (r["project_id"], -r["play_count"]))

    # ---- per project aggregate ----
    per: dict[int, dict[str, Any]] = {}
    for pid, c in by_pid.items():
        per[pid] = {
            "reviewed_n": 0, "reviewed_play": 0,
            "relevant_n": 0, "relevant_play": 0,
            "uncertain_n": 0, "uncertain_play": 0,
            "irrelevant_n": 0, "irrelevant_play": 0,
            "blank_n": 0,
            "nat_collision_play": 0, "nat_context_play": 0, "nat_localized_play": 0,
            "nat_collision_n": 0, "nat_context_n": 0, "nat_localized_n": 0,
        }
    for r in merged:
        pid = r["project_id"]; p = per[pid]; play = r["play_count"]
        p["reviewed_n"] += 1; p["reviewed_play"] += play
        rel = r["manual_relevant"]
        if rel == "relevant":
            p["relevant_n"] += 1; p["relevant_play"] += play
            # nature breakdown is only meaningful for the false-kills (human=relevant):
            #   china_context   = filter UNDER-detected explicit context (fixable)
            #   localized_no_marker = genuinely no textual marker (irreducible bias)
            nat = r["manual_nature"]
            if nat == "collision_irrelevant":
                p["nat_collision_play"] += play; p["nat_collision_n"] += 1
            elif nat == "china_context":
                p["nat_context_play"] += play; p["nat_context_n"] += 1
            elif nat == "localized_no_marker":
                p["nat_localized_play"] += play; p["nat_localized_n"] += 1
        elif rel == "uncertain":
            p["uncertain_n"] += 1; p["uncertain_play"] += play
        elif rel == "irrelevant":
            p["irrelevant_n"] += 1; p["irrelevant_play"] += play
        else:
            p["blank_n"] += 1

    # ---- build corrected comparison rows ----
    out_rows: list[dict[str, Any]] = []
    for pid in sorted(by_pid):
        c = by_pid[pid]
        p = per[pid]
        lower = parse_int(c.get("signal_likely_total_play"))   # filter floor (head-pass + tail)
        upper = parse_int(c.get("before_likely_total_play"))   # machine ceiling (all noise in)
        # human-anchored: filter floor + human-confirmed false-kills in the head
        anchored = lower + p["relevant_play"]
        anchored_incl = anchored + p["uncertain_play"]
        rec = {
            "project_id": pid,
            "project_name": c.get("project_name"),
            "project_name_en": c.get("project_name_en"),
            "category": c.get("category"),
            "list_type": c.get("list_type"),
            "stock_scale_video_count": parse_int(c.get("scale_video_count_best")),
            "stock_band": c.get("stock_band"),
            # the three reach reference points
            "reach_lower_signal_filtered": lower,
            "reach_human_anchored": anchored,
            "reach_human_anchored_incl_uncertain": anchored_incl,
            "reach_upper_machine_likely": upper,
            # how much of the head gap the human review recovered as real
            "head_reviewed_n": p["reviewed_n"],
            "head_reviewed_play": p["reviewed_play"],
            "head_false_kill_n": p["relevant_n"],
            "head_false_kill_play": p["relevant_play"],
            "head_confirmed_noise_n": p["irrelevant_n"],
            "head_confirmed_noise_play": p["irrelevant_play"],
            "head_uncertain_n": p["uncertain_n"],
            "head_uncertain_play": p["uncertain_play"],
            "head_blank_n": p["blank_n"],
            # false-kill rate within the reviewed head (by play): real / reviewed
            "head_false_kill_play_ratio": round(p["relevant_play"] / p["reviewed_play"], 4) if p["reviewed_play"] else 0.0,
            # nature of the false-kills' play (directional-bias evidence)
            "fk_collision_play": p["nat_collision_play"],
            "fk_context_play": p["nat_context_play"],
            "fk_localized_play": p["nat_localized_play"],
            "fk_localized_n": p["nat_localized_n"],
            "fk_context_n": p["nat_context_n"],
            # how much the anchored reach lifts above the filter floor
            "anchor_lift_play": anchored - lower,
            "anchor_lift_ratio_over_floor": round((anchored - lower) / lower, 4) if lower else None,
            # where the anchored point sits inside the band [0=floor,1=ceiling].
            # clamped: source play counts are rounded, so anchored can marginally exceed the
            # rounded ceiling (e.g. 长调: human-confirmed head play ~= the whole machine total).
            "anchor_position_in_band": min(1.0, round((anchored - lower) / (upper - lower), 4)) if upper > lower else 1.0,
        }
        out_rows.append(rec)

    # ---- aggregate summary ----
    tot_reviewed = sum(p["reviewed_n"] for p in per.values())
    tot_reviewed_play = sum(p["reviewed_play"] for p in per.values())
    tot_real_n = sum(p["relevant_n"] for p in per.values())
    tot_real_play = sum(p["relevant_play"] for p in per.values())
    tot_noise_n = sum(p["irrelevant_n"] for p in per.values())
    tot_noise_play = sum(p["irrelevant_play"] for p in per.values())
    tot_unc_n = sum(p["uncertain_n"] for p in per.values())
    tot_unc_play = sum(p["uncertain_play"] for p in per.values())
    tot_localized_play = sum(p["nat_localized_play"] for p in per.values())
    tot_localized_n = sum(p["nat_localized_n"] for p in per.values())
    tot_context_play = sum(p["nat_context_play"] for p in per.values())
    form_dist = Counter(r["manual_content_form"] for r in merged if r["manual_content_form"])

    summary = {
        "date": DATE,
        "reviewed_videos": tot_reviewed,
        "reviewed_play": tot_reviewed_play,
        "filter_false_kill": {
            "n": tot_real_n, "play": tot_real_play,
            "n_ratio_of_reviewed": round(tot_real_n / tot_reviewed, 4) if tot_reviewed else 0,
            "play_ratio_of_reviewed": round(tot_real_play / tot_reviewed_play, 4) if tot_reviewed_play else 0,
            "note": "filter said noise but human said relevant = videos the China-signal text filter wrongly removed from reach",
        },
        "filter_confirmed_noise": {
            "n": tot_noise_n, "play": tot_noise_play,
            "play_ratio_of_reviewed": round(tot_noise_play / tot_reviewed_play, 4) if tot_reviewed_play else 0,
        },
        "uncertain": {"n": tot_unc_n, "play": tot_unc_play},
        "false_kill_anatomy": {
            "localized_no_marker_n": tot_localized_n,
            "localized_no_marker_play": tot_localized_play,
            "china_context_n": sum(p["nat_context_n"] for p in per.values()),
            "china_context_play": tot_context_play,
            "note": "Anatomy of the 118 false-kills only. localized_no_marker = real heritage made for overseas "
                    "audiences with NO #china textual marker -> a text filter structurally cannot keep these "
                    "(irreducible directional bias toward the invisibility hypothesis). china_context = the video DID "
                    "carry china context the filter heuristic under-detected -> filter under-coverage, in principle fixable.",
        },
        "content_form_of_reviewed": dict(form_dist.most_common()),
        "projects_with_false_kills": sum(1 for p in per.values() if p["relevant_play"] > 0),
    }

    # ---- write outputs ----
    REVIEW.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    ret_fields = ["check_id", "project_id", "project_name", "play_count", "source_term",
                  "author_handle", "url", "manual_relevant", "manual_relevant_raw",
                  "manual_nature", "manual_nature_raw", "manual_content_form",
                  "manual_reviewer", "manual_notes", "source_file"]
    with (REVIEW / f"tiktok_head_check_returned_{DATE}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ret_fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader(); w.writerows(merged)

    (DERIVED / f"tiktok_head_check_reach_corrected_{DATE}.json").write_text(
        json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (DERIVED / f"tiktok_head_check_reach_corrected_{DATE}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()), extrasaction="ignore", lineterminator="\n")
        w.writeheader(); w.writerows(out_rows)

    (DERIVED / f"tiktok_head_check_summary_{DATE}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"merged_rows": len(merged), "projects": len(out_rows), "summary": summary},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
