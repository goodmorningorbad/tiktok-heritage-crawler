#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-merge the TikTok × YouTube cross-platform visibility matrix (2026-06-20).

Uses the NEW band-口径 from both platforms:
- TikTok : china-signal filtered band (lower=signal_likely, upper=raw likely)
- YouTube: manual-review backflow band (lower=likely_total_view, upper=inclusive)

METHODOLOGY RED LINES (enforced here):
1. 跨平台不比绝对播放值 — 两平台过滤精度 + 采集深度不同。跨平台模式只按"各平台内部相对位置(reach_band)"判定。
2. YouTube 只深采了 P0 候选(15 项有数据)。其余 29 项是「未深采」,不是「YouTube 零触达」,
   一律标 yt_not_deep_collected,排除出跨平台模式判定 — 绝不臆造"仅 TikTok 可见"。

Inputs:
- data/derived/tiktok_china_signal_filtered_reach_comparison_20260620.json   (44)
- data/derived/youtube_final_project_reach_manual_corrected_20260620.json    (15)
Outputs:
- data/derived/cross_platform_visibility_matrix_20260620.csv / .json
- docs/跨平台可见性矩阵_TikTok_YouTube_20260620.md
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
DOCS = ROOT / "docs"
TT = DERIVED / "tiktok_china_signal_filtered_reach_comparison_20260620.json"
YT = DERIVED / "youtube_final_project_reach_manual_corrected_20260620.json"
DATE = "20260620"

REACH_HIGH_CUT = 0.40   # 各平台内前40%为 reach_high(与 TikTok 分档一致)


def parse_int(v) -> int:
    try:
        return int(float(str(v).replace(",", ""))) if v not in (None, "") else 0
    except Exception:
        return 0


def rank_band(items: list[tuple[int, int]]) -> dict[int, str]:
    """items=[(pid, lower_reach)]. 返回 pid->reach_high/reach_low(按下界排名,前40%为high)。"""
    ordered = sorted(items, key=lambda x: x[1], reverse=True)
    n = len(ordered)
    out = {}
    for i, (pid, _v) in enumerate(ordered):
        out[pid] = "reach_high" if (i + 1) / n <= REACH_HIGH_CUT else "reach_low"
    return out


PATTERN = {
    ("reach_high", "reach_high"): ("both_visible", "双平台可见"),
    ("reach_high", "reach_low"): ("tiktok_led", "TikTok主导(YT相对弱)"),
    ("reach_low", "reach_high"): ("youtube_led", "YouTube主导(TT相对弱)"),
    ("reach_low", "reach_low"): ("both_low", "双平台均低可见"),
}


def main() -> int:
    tt = {int(r["project_id"]): r for r in json.load(TT.open(encoding="utf-8"))}
    yt = {int(r["project_id"]): r for r in json.load(YT.open(encoding="utf-8"))}

    # YouTube 内部 reach_band(只用 15 个有数据项,按 likely 下界排名)
    yt_band = rank_band([(pid, parse_int(r["likely_total_view"])) for pid, r in yt.items()])

    rows = []
    for pid in sorted(tt):
        t = tt[pid]
        tt_band = "reach_high" if t.get("signal_reach_band") == "reach_high" else (
            "reach_unknown" if t.get("signal_reach_band") == "reach_unknown" else "reach_low")
        row = {
            "project_id": pid,
            "project_name": t.get("project_name", ""),
            "project_name_en": t.get("project_name_en", ""),
            "category": t.get("category", ""),
            "list_type": t.get("list_type", ""),
            "tt_stock_band": t.get("stock_band", ""),
            "tt_reach_lower_signal": parse_int(t.get("signal_likely_total_play")),
            "tt_reach_upper_raw": parse_int(t.get("before_likely_total_play")),
            "tt_reach_band": tt_band,
            "tt_quadrant": t.get("signal_quadrant", ""),
        }
        if pid in yt:
            y = yt[pid]
            row.update({
                "yt_status": "collected",
                "yt_reach_lower_likely": parse_int(y.get("likely_total_view")),
                "yt_reach_upper_inclusive": parse_int(y.get("inclusive_total_view")),
                "yt_likely_videos": parse_int(y.get("likely_videos")),
                "yt_reach_band": yt_band[pid],
            })
            if tt_band in ("reach_high", "reach_low"):
                code, label = PATTERN[(tt_band, yt_band[pid])]
            else:
                code, label = "tt_reach_unknown", "TikTok触达档未知"
            row["cross_platform_pattern"] = code
            row["cross_platform_pattern_label"] = label
        else:
            row.update({
                "yt_status": "not_deep_collected",
                "yt_reach_lower_likely": "",
                "yt_reach_upper_inclusive": "",
                "yt_likely_videos": "",
                "yt_reach_band": "",
                "cross_platform_pattern": "yt_not_comparable",
                "cross_platform_pattern_label": "YT未深采·不可比",
            })
        rows.append(row)

    # 跨平台模式排序:可比的在前,按模式分组
    pat_order = {"both_visible": 0, "youtube_led": 1, "tiktok_led": 2, "both_low": 3,
                 "tt_reach_unknown": 4, "yt_not_comparable": 9}
    rows.sort(key=lambda r: (pat_order.get(r["cross_platform_pattern"], 5),
                             -parse_int(r["tt_reach_upper_raw"])))

    fields = list(rows[0].keys())
    with (DERIVED / f"cross_platform_visibility_matrix_{DATE}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    (DERIVED / f"cross_platform_visibility_matrix_{DATE}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # report
    comparable = [r for r in rows if r["yt_status"] == "collected"]
    def short(n):
        n = parse_int(n)
        return f"{n/1e6:.1f}M" if n >= 1e6 else (f"{n/1e3:.0f}K" if n >= 1e3 else str(n))
    lines = [
        f"# 跨平台可见性矩阵 TikTok × YouTube（{DATE}）", "",
        "## 口径红线", "",
        "- **不比绝对播放值**:两平台过滤精度 + 采集深度不同。跨平台模式只按「各平台内部相对位置(reach_band,前40%为high)」判定。",
        "- 两平台触达均为**区间**:TikTok=信号过滤(下)→机器likely(上);YouTube=人工likely(下)→inclusive(上)。",
        f"- YouTube 仅深采 P0 候选,**{len(comparable)} 项**双平台可比;其余 29 项 YouTube **未深采**(非零触达,不可比),排除出模式判定。", "",
        "## 跨平台模式（仅 15 个双平台项目）", "",
        "| 项目 | 模式 | TikTok触达区间 | TT档 | YouTube触达区间 | YT档 |",
        "|---|---|--:|:--:|--:|:--:|",
    ]
    for r in comparable:
        lines.append(
            f"| {r['project_name']} | {r['cross_platform_pattern_label']} "
            f"| {short(r['tt_reach_lower_signal'])}–{short(r['tt_reach_upper_raw'])} | {r['tt_reach_band'].replace('reach_','')} "
            f"| {short(r['yt_reach_lower_likely'])}–{short(r['yt_reach_upper_inclusive'])} | {r['yt_reach_band'].replace('reach_','')} |")
    lines += ["", "## 未深采 YouTube 的 29 项(仅 TikTok 数据,跨平台不可比)", "",
              "、".join(r["project_name"] for r in rows if r["yt_status"] == "not_deep_collected")]
    (DOCS / f"跨平台可见性矩阵_TikTok_YouTube_{DATE}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    from collections import Counter
    print(json.dumps({
        "total_projects": len(rows),
        "cross_platform_comparable": len(comparable),
        "pattern_counts": dict(Counter(r["cross_platform_pattern_label"] for r in comparable)),
        "outputs": [
            f"cross_platform_visibility_matrix_{DATE}.csv/json",
            f"docs/跨平台可见性矩阵_TikTok_YouTube_{DATE}.md",
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
