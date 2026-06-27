#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the data-journalism story deliverables on top of the TikTok
China-signal filtered recalculation (2026-06-20).

This is an ADDITIVE analysis step: it reads frozen/derived inputs and writes new
artifacts only. It does not modify raw collection data or the recalc outputs.

Inputs:
- data/derived/tiktok_china_signal_filtered_reach_comparison_20260620.json  (band + quadrant)
- data/final/tiktok_closed_20260619/row_labels/tiktok_video_relevance_labels_final.ndjson

Outputs:
- data/derived/tiktok_author_concentration_20260620.csv          (谁在传播: top1/top3 作者占比)
- data/derived/tiktok_story_master_table_20260620.csv            (报告入口主表: 存量×触达区间×稀释×象限×作者集中度)
- data/derived/tiktok_head_check_list_20260620.csv               (头部人工核查清单: 定真值+撞词/本土化+内容形态打标)
- docs/figures/story_band_scatter_20260620.svg                   (主图①: 存量×触达 区间散点)
- docs/figures/story_dilution_dumbbell_20260620.svg              (图②: raw→filtered 触达稀释哑铃图)
- docs/figures/story_author_concentration_20260620.svg           (图③: 作者集中度)
- docs/TikTok_story_dashboard_20260620.html                      (自包含展示页, 内联三图+主表)
"""
from __future__ import annotations

import csv
import html
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
FINAL = ROOT / "data/final/tiktok_closed_20260619"
COMPARISON = DERIVED / "tiktok_china_signal_filtered_reach_comparison_20260620.json"
# human-anchored reach from the 378 head-check backflow (optional; overlays anchor point if present)
ANCHORED = DERIVED / "tiktok_head_check_reach_corrected_20260620.json"
HEAD_SUMMARY = DERIVED / "tiktok_head_check_summary_20260620.json"
ROW_LABELS = FINAL / "row_labels/tiktok_video_relevance_labels_final.ndjson"
FIG_DIR = ROOT / "docs/figures"
DATE = "20260620"

# 头部核查清单的取样规则：累计播放占比到此阈值即停，但每项至少/至多这么多条
HEAD_CUM_TARGET = 0.80
HEAD_MIN = 5
HEAD_MAX = 25

LIMIT_NOTE = (
    "触达以中国信号过滤（china_context_hit 或 has_cjk_desc）为下界、机器 likely 为上界，"
    "报区间；区间宽度本身即“身份稀释度”证据。头部由人工核查定真值，长尾用信号过滤估计。"
    "文本方法无法判定无文本线索、纯画面的中国非遗，列为已知局限。"
)


# ---------------------------------------------------------------- utils
def parse_int(v: Any) -> int:
    try:
        if v is None or v == "":
            return 0
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def fmt_short(n: float) -> str:
    n = float(n)
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.0f}K"
    return str(int(n))


def log10p(v: float) -> float:
    return math.log10(max(float(v), 1.0))


# ---------------------------------------------------------------- load
def load_comparison() -> list[dict[str, Any]]:
    return json.loads(COMPARISON.read_text(encoding="utf-8"))


def load_anchor() -> dict[int, dict[str, Any]]:
    """pid -> human-anchored reach record (empty if backflow not run yet)."""
    if not ANCHORED.exists():
        return {}
    return {int(r["project_id"]): r for r in json.loads(ANCHORED.read_text(encoding="utf-8"))}


def load_head_summary() -> dict[str, Any]:
    return json.loads(HEAD_SUMMARY.read_text(encoding="utf-8")) if HEAD_SUMMARY.exists() else {}


def scan_row_labels() -> dict[int, dict[str, Any]]:
    """Per project: dedup likely videos (best record by play), tag china signal,
    accumulate author play for concentration, keep raw-likely head for review."""
    projects: dict[int, dict[str, Any]] = {}
    # videos[pid][vid] = best record (highest play) among likely rows of that video
    videos: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    with ROW_LABELS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            pid = int(d["project_id"])
            projects.setdefault(pid, {
                "project_id": pid,
                "project_name": d.get("project_name", ""),
                "project_name_en": d.get("project_name_en", ""),
                "category": d.get("category", ""),
                "list_type": d.get("list_type", ""),
            })
            if d.get("quality_label") != "likely_relevant":
                continue
            vid = str(d.get("video_id") or "")
            if not vid:
                continue
            cur = videos[pid].get(vid)
            if cur is None or parse_int(d.get("stats_play_count")) > parse_int(cur.get("stats_play_count")):
                videos[pid][vid] = d

    for pid, info in projects.items():
        recs = list(videos.get(pid, {}).values())
        for r in recs:
            r["_signal"] = bool(r.get("china_context_hit")) or bool(r.get("has_cjk_desc"))
            r["_play"] = parse_int(r.get("stats_play_count"))
        # author concentration computed on the signal-filtered likely pool (= attributed reach)
        signal_recs = [r for r in recs if r["_signal"]]
        author_play: dict[str, int] = defaultdict(int)
        for r in signal_recs:
            author_play[str(r.get("author_unique_id") or "(unknown)")] += r["_play"]
        total_signal_play = sum(author_play.values())
        ranked = sorted(author_play.values(), reverse=True)
        top1 = ranked[0] if ranked else 0
        top3 = sum(ranked[:3])
        info["n_signal_videos"] = len(signal_recs)
        info["n_signal_authors"] = len(author_play)
        info["signal_total_play"] = total_signal_play
        info["top1_author_share"] = round(top1 / total_signal_play, 4) if total_signal_play else 0.0
        info["top3_author_share"] = round(top3 / total_signal_play, 4) if total_signal_play else 0.0
        info["_recs"] = recs
    return projects


# ---------------------------------------------------------------- outputs: tables
def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build_author_concentration(projects: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for pid in sorted(projects):
        p = projects[pid]
        conf = "low_n" if p["n_signal_videos"] < 5 else "ok"
        if p["top1_author_share"] >= 0.5:
            mode = "博主中介(头部高度集中)"
        elif p["top1_author_share"] >= 0.25:
            mode = "半集中"
        elif p["n_signal_videos"] == 0:
            mode = "无信号触达"
        else:
            mode = "去中心化(分散偶发)"
        rows.append({
            "project_id": pid,
            "project_name": p["project_name"],
            "category": p["category"],
            "n_signal_videos": p["n_signal_videos"],
            "n_signal_authors": p["n_signal_authors"],
            "signal_total_play": p["signal_total_play"],
            "top1_author_share": p["top1_author_share"],
            "top3_author_share": p["top3_author_share"],
            "diffusion_mode": mode,
            "confidence": conf,
        })
    return rows


def build_master_table(comparison: list[dict[str, Any]], projects: dict[int, dict[str, Any]],
                       anchor: dict[int, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    anchor = anchor or {}
    by_pid = {int(c["project_id"]): c for c in comparison}
    rows = []
    for pid in sorted(by_pid):
        c = by_pid[pid]
        p = projects.get(pid, {})
        a = anchor.get(pid, {})
        raw = parse_int(c.get("before_likely_total_play"))
        filt = parse_int(c.get("signal_likely_total_play"))
        anc = parse_int(a.get("reach_human_anchored")) if a else filt
        rows.append({
            "project_id": pid,
            "project_name": c.get("project_name"),
            "project_name_en": c.get("project_name_en"),
            "category": c.get("category"),
            "list_type": c.get("list_type"),
            "stock_scale_video_count": parse_int(c.get("scale_video_count_best")),
            "stock_band": c.get("stock_band"),
            "reach_lower_signal_filtered": filt,
            "reach_human_anchored": anc,
            "head_false_kill_play": parse_int(a.get("head_false_kill_play")) if a else 0,
            "head_false_kill_n": parse_int(a.get("head_false_kill_n")) if a else 0,
            "head_confirmed_noise_n": parse_int(a.get("head_confirmed_noise_n")) if a else 0,
            "fk_localized_n": parse_int(a.get("fk_localized_n")) if a else 0,
            "reach_upper_raw_likely": raw,
            "reach_band_width_ratio": c.get("play_drop_ratio"),   # = (raw-filt)/raw = 稀释度
            "identity_dilution_pct": c.get("play_drop_ratio"),
            "no_china_signal_unique_ratio": c.get("no_china_signal_unique_ratio"),
            "quadrant_before": c.get("before_quadrant"),
            "quadrant_after_filter": c.get("signal_quadrant"),
            "quadrant_label_after": c.get("signal_quadrant_label"),
            "quadrant_changed": c.get("quadrant_changed_after_signal_filter"),
            "reach_tier_after": c.get("signal_likely_reach_tier"),
            "top1_author_share": p.get("top1_author_share", ""),
            "top3_author_share": p.get("top3_author_share", ""),
            "n_signal_videos": p.get("n_signal_videos", ""),
            "diffusion_confidence": "low_n" if p.get("n_signal_videos", 0) < 5 else "ok",
            "limitation_note": LIMIT_NOTE,
        })
    # sort by upper-bound reach desc for a readable master table
    rows.sort(key=lambda r: r["reach_upper_raw_likely"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank_by_raw_reach"] = i
    return rows


def build_head_check_list(projects: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Top videos of the RAW likely pool per project, cumulating to HEAD_CUM_TARGET of
    play (bounded by HEAD_MIN/HEAD_MAX). Each row gets blank manual columns so a human
    can, in one pass: (a) confirm relevance, (b) distinguish 撞词 vs 本土化, (c) code 内容形态."""
    out = []
    for pid in sorted(projects):
        p = projects[pid]
        recs = sorted(p.get("_recs", []), key=lambda r: r["_play"], reverse=True)
        total = sum(r["_play"] for r in recs) or 1
        cum = 0
        chosen = []
        for r in recs:
            chosen.append(r)
            cum += r["_play"]
            if len(chosen) >= HEAD_MIN and cum / total >= HEAD_CUM_TARGET:
                break
            if len(chosen) >= HEAD_MAX:
                break
        for idx, r in enumerate(chosen, 1):
            out.append({
                "check_id": f"HC-{pid:02d}-{idx:02d}",
                "project_id": pid,
                "project_name": p["project_name"],
                "video_rank_in_project": idx,
                "play_count": r["_play"],
                "cum_play_share": round(sum(x["_play"] for x in chosen[:idx]) / total, 4),
                "passes_china_signal_filter": r["_signal"],
                "source_term": r.get("source_term", ""),
                "author_handle": r.get("author_unique_id", ""),
                "url": r.get("web_url", ""),
                "caption": (r.get("desc") or "")[:300],
                "hashtags": json.dumps(r.get("hashtags", []), ensure_ascii=False),
                # ---- 人工填写列 ----
                "manual_relevant": "",           # 相关 / 不相关 / 拿不准
                "manual_nature": "",             # 撞词无关 / 有中国语境 / 本土化无中国标记
                "manual_content_form": "",       # 教学 / 展示表演 / 视觉奇观 / vlog记录 / 卖货 / 其他
                "manual_reviewer": "",
                "manual_notes": "",
            })
    return out


# ---------------------------------------------------------------- outputs: SVG figures
def svg_open(w: int, h: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]


def fig_band_scatter(comparison: list[dict[str, Any]], anchor: dict[int, dict[str, Any]] | None = None) -> str:
    anchor = anchor or {}
    W, H = 960, 660
    ML, MR, MT, MB = 70, 30, 60, 70
    PW, PH = W - ML - MR, H - MT - MB
    pts = []
    for c in comparison:
        stock = parse_int(c.get("scale_video_count_best"))
        raw = parse_int(c.get("before_likely_total_play"))
        filt = parse_int(c.get("signal_likely_total_play"))
        if stock <= 0 and raw <= 0:
            continue
        pid = int(c["project_id"])
        a = anchor.get(pid)
        # anchored only meaningful where the human review actually recovered head play
        anc = parse_int(a.get("reach_human_anchored")) if a and parse_int(a.get("head_false_kill_play")) > 0 else 0
        pts.append({"name": c.get("project_name", ""), "stock": stock, "raw": raw, "filt": filt,
                    "anchor": anc, "quad": c.get("signal_quadrant", "")})
    xs = [log10p(p["stock"]) for p in pts]
    ys = [log10p(max(p["raw"], 1)) for p in pts] + [log10p(max(p["filt"], 1)) for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    x0 -= 0.2; x1 += 0.2; y0 -= 0.3; y1 += 0.3
    xmed = median([log10p(p["stock"]) for p in pts])
    ymed = median([log10p(max(p["filt"], 1)) for p in pts])

    def X(lv): return ML + (lv - x0) / (x1 - x0) * PW
    def Y(lv): return MT + PH - (lv - y0) / (y1 - y0) * PH

    s = svg_open(W, H)
    s.append(f'<text x="{W/2}" y="26" text-anchor="middle" font-size="18" font-weight="700">'
             f'图① 存量 × 触达：44 项中国非遗 TikTok 可见性矩阵</text>')
    s.append(f'<text x="{W/2}" y="44" text-anchor="middle" font-size="11" fill="#666">'
             f'竖线=触达区间（下端 中国信号过滤 / 上端 机器 likely）；绿菱=头部378条人工核查后的真值锚点；象限按中位线划分</text>')
    # quadrant background tints
    qx, qy = X(xmed), Y(ymed)
    s.append(f'<rect x="{qx}" y="{MT}" width="{ML+PW-qx}" height="{qy-MT}" fill="#e7f6f0"/>')          # 右上 真出海
    s.append(f'<rect x="{ML}" y="{qy}" width="{qx-ML}" height="{MT+PH-qy}" fill="#f5f5f7"/>')          # 左下 隐形
    s.append(f'<rect x="{qx}" y="{qy}" width="{ML+PW-qx}" height="{MT+PH-qy}" fill="#fdeee0"/>')       # 右下 自循环
    s.append(f'<rect x="{ML}" y="{MT}" width="{qx-ML}" height="{qy-MT}" fill="#eaf1fd"/>')             # 左上 破圈
    # axes
    s.append(f'<line x1="{ML}" y1="{MT+PH}" x2="{ML+PW}" y2="{MT+PH}" stroke="#333"/>')
    s.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+PH}" stroke="#333"/>')
    s.append(f'<line x1="{qx}" y1="{MT}" x2="{qx}" y2="{MT+PH}" stroke="#bbb" stroke-dasharray="4 4"/>')
    s.append(f'<line x1="{ML}" y1="{qy}" x2="{ML+PW}" y2="{qy}" stroke="#bbb" stroke-dasharray="4 4"/>')
    # y gridlines at each order of magnitude
    for e in range(int(math.floor(y0)), int(math.ceil(y1)) + 1):
        yy = Y(e)
        if MT <= yy <= MT + PH:
            s.append(f'<text x="{ML-8}" y="{yy+4}" text-anchor="end" font-size="10" fill="#888">'
                     f'{fmt_short(10**e)}</text>')
    for e in range(int(math.floor(x0)), int(math.ceil(x1)) + 1):
        xx = X(e)
        if ML <= xx <= ML + PW:
            s.append(f'<text x="{xx}" y="{MT+PH+16}" text-anchor="middle" font-size="10" fill="#888">'
                     f'{fmt_short(10**e)}</text>')
    s.append(f'<text x="{ML+PW/2}" y="{H-22}" text-anchor="middle" font-size="12" fill="#444">'
             f'存量（challenge 视频规模，对数）→</text>')
    s.append(f'<text x="20" y="{MT+PH/2}" text-anchor="middle" font-size="12" fill="#444" '
             f'transform="rotate(-90 20 {MT+PH/2})">触达（相关播放量，对数）→</text>')
    # quadrant captions
    s.append(f'<text x="{ML+PW-8}" y="{MT+14}" text-anchor="end" font-size="11" fill="#1f9d7a" font-weight="700">真·规模化出海</text>')
    s.append(f'<text x="{ML+8}" y="{MT+14}" font-size="11" fill="#3b82f6" font-weight="700">小而精破圈</text>')
    s.append(f'<text x="{ML+PW-8}" y="{MT+PH-8}" text-anchor="end" font-size="11" fill="#d88923" font-weight="700">高存量低触达·自产自销</text>')
    s.append(f'<text x="{ML+8}" y="{MT+PH-8}" font-size="11" fill="#888" font-weight="700">近乎隐形</text>')
    # points + band bars
    for p in pts:
        x = X(log10p(p["stock"]))
        yr = Y(log10p(max(p["raw"], 1)))
        yf = Y(log10p(max(p["filt"], 1)))
        s.append(f'<line x1="{x:.1f}" y1="{yr:.1f}" x2="{x:.1f}" y2="{yf:.1f}" stroke="#c0392b" stroke-width="1.4" opacity="0.55"/>')
        s.append(f'<circle cx="{x:.1f}" cy="{yr:.1f}" r="2.4" fill="#c0392b" opacity="0.5"/>')
        s.append(f'<circle cx="{x:.1f}" cy="{yf:.1f}" r="3.4" fill="#16557a"/>')
        # human-anchored point (green diamond) where head review recovered real play
        if p["anchor"] > p["filt"]:
            ya = Y(log10p(max(p["anchor"], 1)))
            s.append(f'<path d="M {x:.1f} {ya-4:.1f} L {x+4:.1f} {ya:.1f} L {x:.1f} {ya+4:.1f} L {x-4:.1f} {ya:.1f} Z" '
                     f'fill="#1f9d4d" stroke="#fff" stroke-width="0.6"/>')
        s.append(f'<text x="{x+5:.1f}" y="{yf-4:.1f}" font-size="9" fill="#222">{esc(p["name"])}</text>')
    # legend
    s.append(f'<circle cx="{ML+10}" cy="{MT+PH-60}" r="2.4" fill="#c0392b" opacity="0.6"/>'
             f'<text x="{ML+18}" y="{MT+PH-56}" font-size="10" fill="#333">上界 机器 likely（含撞词噪声）</text>')
    s.append(f'<path d="M {ML+10} {MT+PH-48} l 4 4 l -4 4 l -4 -4 Z" fill="#1f9d4d"/>'
             f'<text x="{ML+18}" y="{MT+PH-40}" font-size="10" fill="#333">人工锚定（头部378条核查后真值）</text>')
    s.append(f'<circle cx="{ML+10}" cy="{MT+PH-28}" r="3.4" fill="#16557a"/>'
             f'<text x="{ML+18}" y="{MT+PH-24}" font-size="10" fill="#333">下界 中国信号过滤</text>')
    s.append('</svg>')
    return "\n".join(s)


def fig_dilution_dumbbell(comparison: list[dict[str, Any]]) -> str:
    rows = [c for c in comparison if parse_int(c.get("before_likely_total_play")) > 0]
    rows.sort(key=lambda c: float(c.get("play_drop_ratio") or 0), reverse=True)
    n = len(rows)
    rowh = 15
    MT, MB, ML, MR = 70, 40, 200, 120
    PH = n * rowh
    H = MT + PH + MB
    W = 980
    PW = W - ML - MR
    plays = [parse_int(c.get("before_likely_total_play")) for c in rows] + \
            [max(parse_int(c.get("signal_likely_total_play")), 1) for c in rows]
    lo, hi = log10p(min(plays)), log10p(max(plays))
    lo -= 0.2; hi += 0.2

    def X(v): return ML + (log10p(max(v, 1)) - lo) / (hi - lo) * PW

    s = svg_open(W, H)
    s.append(f'<text x="{W/2}" y="26" text-anchor="middle" font-size="18" font-weight="700">'
             f'图② 触达稀释：机器 likely → 中国信号过滤后</text>')
    s.append(f'<text x="{W/2}" y="44" text-anchor="middle" font-size="11" fill="#666">'
             f'横条越长 = 撞词/无中国信号占比越高 = 该非遗“身份被稀释”越严重（按缩水比例降序）</text>')
    for e in range(int(math.floor(lo)), int(math.ceil(hi)) + 1):
        xx = X(10**e)
        if ML <= xx <= ML + PW:
            s.append(f'<line x1="{xx}" y1="{MT}" x2="{xx}" y2="{MT+PH}" stroke="#eee"/>')
            s.append(f'<text x="{xx}" y="{MT-6}" text-anchor="middle" font-size="10" fill="#999">{fmt_short(10**e)}</text>')
    for i, c in enumerate(rows):
        y = MT + i * rowh + rowh / 2
        raw = parse_int(c.get("before_likely_total_play"))
        filt = parse_int(c.get("signal_likely_total_play"))
        drop = float(c.get("play_drop_ratio") or 0)
        xr, xf = X(raw), X(filt)
        col = "#c0392b" if drop >= 0.7 else ("#d88923" if drop >= 0.4 else "#1f9d7a")
        s.append(f'<text x="{ML-8}" y="{y+3}" text-anchor="end" font-size="10" fill="#333">{esc(c.get("project_name"))}</text>')
        s.append(f'<line x1="{xf:.1f}" y1="{y:.1f}" x2="{xr:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="2.2" opacity="0.6"/>')
        s.append(f'<circle cx="{xf:.1f}" cy="{y:.1f}" r="3.2" fill="#16557a"/>')
        s.append(f'<circle cx="{xr:.1f}" cy="{y:.1f}" r="3.2" fill="{col}"/>')
        s.append(f'<text x="{ML+PW+8}" y="{y+3}" font-size="9" fill="{col}">-{drop*100:.0f}%</text>')
    s.append(f'<circle cx="{ML}" cy="{MT+PH+26}" r="3.2" fill="#16557a"/>'
             f'<text x="{ML+10}" y="{MT+PH+30}" font-size="10" fill="#333">过滤后(下界)</text>')
    s.append(f'<circle cx="{ML+150}" cy="{MT+PH+26}" r="3.2" fill="#c0392b"/>'
             f'<text x="{ML+160}" y="{MT+PH+30}" font-size="10" fill="#333">机器 likely(上界)</text>')
    s.append('</svg>')
    return "\n".join(s)


def fig_author_concentration(concentration: list[dict[str, Any]]) -> str:
    rows = [r for r in concentration if r["n_signal_videos"] > 0]
    rows.sort(key=lambda r: r["top1_author_share"], reverse=True)
    n = len(rows)
    rowh = 16
    MT, MB, ML, MR = 70, 40, 200, 150
    PH = n * rowh
    W = 900
    H = MT + PH + MB
    PW = W - ML - MR
    s = svg_open(W, H)
    s.append(f'<text x="{W/2}" y="26" text-anchor="middle" font-size="18" font-weight="700">'
             f'图③ 谁在传播：头部账号集中度（top1 作者播放占比）</text>')
    s.append(f'<text x="{W/2}" y="44" text-anchor="middle" font-size="11" fill="#666">'
             f'红=单一博主中介（一个号扛起大半触达）；蓝=去中心化偶发爆红。仅统计中国信号过滤后触达池</text>')
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        xx = ML + frac * PW
        s.append(f'<line x1="{xx}" y1="{MT}" x2="{xx}" y2="{MT+PH}" stroke="#eee"/>')
        s.append(f'<text x="{xx}" y="{MT-6}" text-anchor="middle" font-size="10" fill="#999">{int(frac*100)}%</text>')
    for i, r in enumerate(rows):
        y = MT + i * rowh
        share = r["top1_author_share"]
        col = "#c0392b" if share >= 0.5 else ("#d88923" if share >= 0.25 else "#3b82f6")
        bw = share * PW
        s.append(f'<text x="{ML-8}" y="{y+12}" text-anchor="end" font-size="10" fill="#333">{esc(r["project_name"])}</text>')
        s.append(f'<rect x="{ML}" y="{y+3}" width="{bw:.1f}" height="{rowh-6}" fill="{col}" opacity="0.85"/>')
        tag = "" if r["confidence"] == "ok" else " ⚠n小"
        s.append(f'<text x="{ML+bw+6:.1f}" y="{y+12}" font-size="9" fill="#555">{share*100:.0f}% '
                 f'({r["n_signal_videos"]}视频/{r["n_signal_authors"]}号){esc(tag)}</text>')
    s.append('</svg>')
    return "\n".join(s)


# ---------------------------------------------------------------- HTML
def build_html(master: list[dict[str, Any]], head_list: list[dict[str, Any]],
               figs: dict[str, str], head_summary: dict[str, Any] | None = None) -> str:
    head_summary = head_summary or {}
    changed = [m for m in master if str(m.get("quadrant_changed")).lower() == "true"]
    n_proj = len(master)
    n_head = len(head_list)
    rows_html = []
    for m in master:
        chg = "✔" if str(m.get("quadrant_changed")).lower() == "true" else ""
        anc = m.get("reach_human_anchored")
        fk = parse_int(m.get("head_false_kill_play"))
        anc_cell = fmt_short(anc) + (" ↑" if fk > 0 else "") if anc not in ("", None) else "–"
        rows_html.append(
            "<tr>"
            f"<td>{m['rank_by_raw_reach']}</td>"
            f"<td>{esc(m['project_name'])}</td>"
            f"<td>{esc(m['category'])}</td>"
            f"<td class='num'>{fmt_short(m['stock_scale_video_count'])}</td>"
            f"<td class='num'>{fmt_short(m['reach_lower_signal_filtered'])} – {fmt_short(m['reach_upper_raw_likely'])}</td>"
            f"<td class='num'>{anc_cell}</td>"
            f"<td class='num'>{float(m['identity_dilution_pct'] or 0)*100:.0f}%</td>"
            f"<td>{esc(m['quadrant_after_filter'])} <b>{chg}</b></td>"
            f"<td class='num'>{(str(round(float(m['top1_author_share'])*100))+'%') if m['top1_author_share'] not in ('', None) else '–'}</td>"
            "</tr>"
        )

    # head-check summary block
    hc_block = ""
    if head_summary:
        fk = head_summary.get("filter_false_kill", {})
        cn = head_summary.get("filter_confirmed_noise", {})
        an = head_summary.get("false_kill_anatomy", {})
        hc_block = (
            f'<h2>④ 头部人工核查：把区间收成真值</h2>'
            f'<p class="sub">一句话：378 条机器判 likely、却被中国信号过滤剔除的头部视频，逐条人工裁决——'
            f'{int(cn.get("play_ratio_of_reviewed",0)*100)}% 的播放确属噪声（过滤方向正确），'
            f'但 {int(fk.get("play_ratio_of_reviewed",0)*100)}%（{fmt_short(fk.get("play",0))}）是被误杀的真内容。</p>'
            f'<div class="kpis">'
            f'<div class="kpi"><b>{head_summary.get("reviewed_videos",0)}</b>头部逐条核查</div>'
            f'<div class="kpi"><b>{cn.get("n",0)}</b>确认噪声（过滤对了）</div>'
            f'<div class="kpi"><b>{fk.get("n",0)}</b>误杀真内容</div>'
            f'<div class="kpi"><b>{fmt_short(an.get("localized_no_marker_play",0))}</b>本土化无标记<span style="font-size:11px;color:#888"> 不可消除</span></div>'
            f'</div>'
            f'<div class="note">误杀的真内容分两类成因：'
            f'<b>本土化无中国标记 {an.get("localized_no_marker_n",0)} 条 / {fmt_short(an.get("localized_no_marker_play",0))}</b>'
            f'（出海做给外国人看、不打 #china，文本过滤结构上救不了——指向不可消除的方向性偏差，太极/木拱桥/伊玛堪居多）；'
            f'<b>漏检的中国语境 {an.get("china_context_n",0)} 条 / {fmt_short(an.get("china_context_play",0))}</b>'
            f'（其实有中国语境，过滤启发式没识别到——原则上可补，京剧/宣纸居多）。'
            f'两个极端：福船 25 条头部全数确认噪声 → 真实触达仅 10 万；长调底线 36 万、人工确认 1.5 亿全真（跨境蒙古族，零中文标记，过滤砍掉 99.8%）。</div>'
        )
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TikTok 中国非遗可见性 · 数据故事面板 {DATE}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#fafafa;color:#1a1a1a;}}
 .wrap{{max-width:1040px;margin:0 auto;padding:28px 20px 80px;}}
 h1{{font-size:24px;margin:0 0 4px;}} h2{{font-size:18px;margin:34px 0 10px;border-left:4px solid #16557a;padding-left:10px;}}
 .sub{{color:#666;font-size:13px;margin-bottom:18px;}}
 .note{{background:#fff8e6;border:1px solid #f0d999;border-radius:8px;padding:12px 14px;font-size:13px;color:#5a4a1a;margin:16px 0;}}
 .fig{{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:10px;margin:14px 0;overflow-x:auto;}}
 .fig svg{{max-width:100%;height:auto;display:block;margin:0 auto;}}
 table{{border-collapse:collapse;width:100%;font-size:12.5px;background:#fff;}}
 th,td{{border:1px solid #e5e5e5;padding:5px 8px;text-align:left;}} th{{background:#f0f4f8;position:sticky;top:0;}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums;}}
 .kpis{{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0;}}
 .kpi{{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:12px 16px;flex:1;min-width:150px;}}
 .kpi b{{font-size:22px;display:block;color:#16557a;}}
</style></head><body><div class="wrap">
<h1>中国非遗在 TikTok 的海外可见性 · 数据故事面板</h1>
<div class="sub">单平台收口版（2026-06-20，已应用中国信号硬过滤）。跨平台（含 YouTube）待人工回流后合并。</div>
<div class="kpis">
 <div class="kpi"><b>{n_proj}</b>非遗项目</div>
 <div class="kpi"><b>{len(changed)}</b>过滤后象限改变</div>
 <div class="kpi"><b>{head_summary.get('reviewed_videos', n_head)}</b>头部已人工核查视频</div>
</div>
<div class="note">{esc(LIMIT_NOTE)}</div>

<h2>① 存量 × 触达矩阵（核心图）</h2>
<p class="sub">一句话：可被“功能化”的非遗（春节/太极/京剧）落在右上真·出海区；地方戏曲、濒危技艺（福船/伊玛堪/送王船）沉到左下近乎隐形区——差异巨大且有规律。</p>
<div class="fig">{figs['scatter']}</div>

<h2>② 触达稀释（原创发现）</h2>
<p class="sub">一句话：有海外同名混淆物的非遗（书法撞各国手写、福船撞泛词），机器口径触达大幅缩水——身份被稀释的量化证据。</p>
<div class="fig">{figs['dumbbell']}</div>

<h2>③ 谁在传播（头部集中度）</h2>
<p class="sub">一句话：部分非遗的“出海”实为单一博主独力支撑（红），抗风险弱；少数实现去中心化扩散（蓝）。</p>
<div class="fig">{figs['author']}</div>

{hc_block}

<h2>项目级主表</h2>
<p class="sub">「人工锚定」= 中国信号过滤下界 + 头部人工确认的误杀真内容；↑ 表示该项触达被人工上修。</p>
<table><thead><tr>
<th>#</th><th>项目</th><th>类别</th><th>存量</th><th>触达区间(下–上)</th><th>人工锚定</th><th>稀释%</th><th>过滤后象限</th><th>top1占比</th>
</tr></thead><tbody>
{''.join(rows_html)}
</tbody></table>
<p class="sub" style="margin-top:10px">数据文件：tiktok_story_master_table_{DATE}.csv / tiktok_author_concentration_{DATE}.csv /
tiktok_head_check_list_{DATE}.csv（头部人工核查清单，{n_head} 条）。</p>
</div></body></html>"""


def main() -> int:
    comparison = load_comparison()
    projects = scan_row_labels()
    anchor = load_anchor()
    head_summary = load_head_summary()

    concentration = build_author_concentration(projects)
    master = build_master_table(comparison, projects, anchor)
    head_list = build_head_check_list(projects)

    write_csv(DERIVED / f"tiktok_author_concentration_{DATE}.csv", concentration,
              list(concentration[0].keys()))
    write_csv(DERIVED / f"tiktok_story_master_table_{DATE}.csv", master,
              list(master[0].keys()))
    write_csv(DERIVED / f"tiktok_head_check_list_{DATE}.csv", head_list,
              list(head_list[0].keys()))

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    figs = {
        "scatter": fig_band_scatter(comparison, anchor),
        "dumbbell": fig_dilution_dumbbell(comparison),
        "author": fig_author_concentration(concentration),
    }
    (FIG_DIR / f"story_band_scatter_{DATE}.svg").write_text(figs["scatter"], encoding="utf-8")
    (FIG_DIR / f"story_dilution_dumbbell_{DATE}.svg").write_text(figs["dumbbell"], encoding="utf-8")
    (FIG_DIR / f"story_author_concentration_{DATE}.svg").write_text(figs["author"], encoding="utf-8")

    html_path = ROOT / f"docs/TikTok_story_dashboard_{DATE}.html"
    html_path.write_text(build_html(master, head_list, figs, head_summary), encoding="utf-8")

    print(json.dumps({
        "projects": len(master),
        "quadrant_changed": sum(1 for m in master if str(m.get("quadrant_changed")).lower() == "true"),
        "head_check_videos": len(head_list),
        "author_concentration_rows": len(concentration),
        "outputs": {
            "master_table": str(DERIVED / f"tiktok_story_master_table_{DATE}.csv"),
            "author_concentration": str(DERIVED / f"tiktok_author_concentration_{DATE}.csv"),
            "head_check_list": str(DERIVED / f"tiktok_head_check_list_{DATE}.csv"),
            "dashboard_html": str(html_path),
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
