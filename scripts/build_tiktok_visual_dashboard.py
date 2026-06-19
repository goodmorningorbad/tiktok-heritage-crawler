#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an internal TikTok analysis visualization dashboard.

Inputs are manual-corrected/closed TikTok artifacts. Output is a standalone HTML
file for narrative analysis; raw/derived inputs are not modified.
"""
from __future__ import annotations

import csv
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "data/derived/tiktok_manual_corrected_final_project_findings_20260619.csv"
MATRIX = ROOT / "data/derived/project_stock_reach_matrix_manual_corrected.csv"
OUT = ROOT / "docs/TikTok_收口数据可视化_dashboard_20260619.html"
FIG_DIR = ROOT / "docs/figures"
QUAD_SVG = FIG_DIR / "tiktok_quadrant_bubble_20260619.svg"
TIER_SVG = FIG_DIR / "tiktok_final_tier_distribution_20260619.svg"
NOISE_SVG = FIG_DIR / "tiktok_noise_and_manual_impact_20260619.svg"
SUMMARY_JSON = ROOT / "data/derived/tiktok_visual_dashboard_summary_20260619.json"

TIER_LABELS = {
    "T1_scale_export": "T1 规模化出海",
    "T1_scale_export_with_noise_risk": "T1 噪声风险头部",
    "T2_small_breakout": "T2 小众破圈",
    "T3_domestic_or_self_circulating": "T3 国内/自循环",
    "T0_false_breakout_demoted": "T0 假破圈剔除",
    "T4_near_invisible_noise_checked": "T4 近不可见/已查噪",
    "T4_near_invisible": "T4 近不可见",
}
TIER_ORDER = [
    "T1_scale_export",
    "T1_scale_export_with_noise_risk",
    "T2_small_breakout",
    "T3_domestic_or_self_circulating",
    "T0_false_breakout_demoted",
    "T4_near_invisible_noise_checked",
    "T4_near_invisible",
]
TIER_COLORS = {
    "T1_scale_export": "#1f9d7a",
    "T1_scale_export_with_noise_risk": "#d88923",
    "T2_small_breakout": "#3b82f6",
    "T3_domestic_or_self_circulating": "#8b5cf6",
    "T0_false_breakout_demoted": "#dc2626",
    "T4_near_invisible_noise_checked": "#64748b",
    "T4_near_invisible": "#94a3b8",
}
QUAD_POS = {
    "stock_low__reach_low": (0, 0),
    "stock_high__reach_low": (1, 0),
    "stock_low__reach_high": (0, 1),
    "stock_high__reach_high": (1, 1),
}
QUAD_LABELS = {
    "stock_high__reach_high": "高存量 × 高触达：真规模化候选",
    "stock_low__reach_high": "低存量 × 高触达：小众破圈/假亮点待辨",
    "stock_high__reach_low": "高存量 × 低触达：弱外溢/国内自循环",
    "stock_low__reach_low": "低存量 × 低触达：近不可见或已剔除",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def fmt_int(v: Any) -> str:
    n = int(round(num(v)))
    return f"{n:,}"


def fmt_short(v: Any) -> str:
    n = num(v)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(int(n))


def esc(s: Any) -> str:
    return html.escape(str(s or ""), quote=True)


def log_scale(value: float, min_v: float, max_v: float, out_min: float, out_max: float) -> float:
    value = max(value, 1.0)
    min_v = max(min_v, 1.0)
    max_v = max(max_v, min_v + 1)
    lv = math.log10(value)
    lmin = math.log10(min_v)
    lmax = math.log10(max_v)
    if lmax == lmin:
        return (out_min + out_max) / 2
    return out_min + (lv - lmin) / (lmax - lmin) * (out_max - out_min)


def tier_dist_svg(rows: list[dict[str, str]]) -> str:
    counts = Counter(r["final_tier"] for r in rows)
    width, height = 920, 360
    left, top, bar_h, gap = 250, 42, 26, 16
    max_count = max(counts.values()) if counts else 1
    parts = [svg_header(width, height)]
    parts.append('<text x="24" y="28" class="svg-title">最终分层分布：先按叙事角色看，不按项目清单顺序看</text>')
    y = top
    for tier in TIER_ORDER:
        c = counts.get(tier, 0)
        if c == 0:
            continue
        w = 560 * c / max_count
        color = TIER_COLORS.get(tier, "#334155")
        parts.append(f'<text x="24" y="{y+19}" class="svg-label">{esc(TIER_LABELS.get(tier,tier))}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="7" fill="{color}"/>')
        parts.append(f'<text x="{left+w+12:.1f}" y="{y+19}" class="svg-value">{c} 项</text>')
        y += bar_h + gap
    parts.append(svg_footer())
    return "\n".join(parts)


def quadrant_svg(rows: list[dict[str, str]]) -> str:
    width, height = 980, 680
    ml, mt, plot_w, plot_h = 110, 72, 800, 520
    mid_x = ml + plot_w / 2
    mid_y = mt + plot_h / 2
    plays = [max(num(r["likely_total_play"]), 1) for r in rows]
    min_play, max_play = min(plays), max(plays)
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        buckets[r["quadrant"]].append(r)
    for b in buckets.values():
        b.sort(key=lambda r: -num(r["likely_total_play"]))
    offsets = {}
    for quad, arr in buckets.items():
        for i, r in enumerate(arr):
            offsets[r["project_id"]] = ((i % 5) - 2, (i // 5) - 1)

    parts = [svg_header(width, height)]
    parts.append('<text x="24" y="34" class="svg-title">TikTok 存量 × 相关触达矩阵（人工回流后）</text>')
    # quadrants
    fills = {
        "stock_high__reach_high": "#dcfce7",
        "stock_low__reach_high": "#dbeafe",
        "stock_high__reach_low": "#fef3c7",
        "stock_low__reach_low": "#f1f5f9",
    }
    rects = {
        "stock_low__reach_high": (ml, mt, plot_w/2, plot_h/2),
        "stock_high__reach_high": (mid_x, mt, plot_w/2, plot_h/2),
        "stock_low__reach_low": (ml, mid_y, plot_w/2, plot_h/2),
        "stock_high__reach_low": (mid_x, mid_y, plot_w/2, plot_h/2),
    }
    for q, (x, y, w, h) in rects.items():
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fills[q]}" stroke="#cbd5e1"/>')
        lx = x + 18
        ly = y + 30
        parts.append(f'<text x="{lx}" y="{ly}" class="svg-quad-label">{esc(QUAD_LABELS[q])}</text>')
    parts.append(f'<line x1="{mid_x}" y1="{mt}" x2="{mid_x}" y2="{mt+plot_h}" stroke="#94a3b8" stroke-dasharray="5 6"/>')
    parts.append(f'<line x1="{ml}" y1="{mid_y}" x2="{ml+plot_w}" y2="{mid_y}" stroke="#94a3b8" stroke-dasharray="5 6"/>')
    parts.append(f'<text x="{ml+plot_w/2}" y="{height-35}" text-anchor="middle" class="svg-axis">存量：低 → 高（hashtag videoCount 定性分档）</text>')
    parts.append(f'<text x="28" y="{mt+plot_h/2}" transform="rotate(-90 28 {mt+plot_h/2})" text-anchor="middle" class="svg-axis">相关触达：低 → 高（likely play）</text>')

    # points
    for r in rows:
        q = r["quadrant"]
        qx, qy = QUAD_POS.get(q, (0, 0))
        base_x = ml + plot_w * (0.25 if qx == 0 else 0.75)
        base_y = mt + plot_h * (0.75 if qy == 0 else 0.25)
        ox, oy = offsets.get(r["project_id"], (0, 0))
        x = base_x + ox * 55
        y = base_y + oy * 42
        radius = 7 + log_scale(num(r["likely_total_play"]), min_play, max_play, 0, 18)
        color = TIER_COLORS.get(r["final_tier"], "#334155")
        stroke = "#111827" if r.get("manual_audit_verdict") else "#ffffff"
        title = f"{r['project_name']}｜{TIER_LABELS.get(r['final_tier'], r['final_tier'])}｜播放 {fmt_short(r['likely_total_play'])}｜噪声 {r['low_relevance_play_ratio']}"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" fill-opacity="0.88" stroke="{stroke}" stroke-width="2"><title>{esc(title)}</title></circle>')
        if num(r["likely_total_play"]) >= 50_000_000 or r["final_tier"].startswith("T0"):
            parts.append(f'<text x="{x+radius+4:.1f}" y="{y+4:.1f}" class="svg-small">{esc(r["project_name"][:8])}</text>')
    # legend
    lx, ly = ml, height - 70
    for i, tier in enumerate(TIER_ORDER[:6]):
        x = lx + (i % 3) * 260
        y = ly + (i // 3) * 26
        parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{TIER_COLORS[tier]}"/>')
        parts.append(f'<text x="{x+14}" y="{y+5}" class="svg-small">{esc(TIER_LABELS[tier])}</text>')
    parts.append(svg_footer())
    return "\n".join(parts)


def noise_svg(rows: list[dict[str, str]]) -> str:
    width, height = 980, 420
    top_noise = sorted(rows, key=lambda r: num(r["low_relevance_play_ratio"]), reverse=True)[:12]
    manual = sorted([r for r in rows if r.get("manual_audit_verdict") or num(r.get("manual_reach_play_delta")) < 0], key=lambda r: num(r.get("manual_reach_play_delta")))
    parts = [svg_header(width, height)]
    parts.append('<text x="24" y="34" class="svg-title">噪声与人工回流：哪些“高触达”不能直接讲成传播成功</text>')
    # left bars noise ratio
    parts.append('<text x="24" y="70" class="svg-subtitle">低相关播放占比 Top 12</text>')
    x0, y0, maxw = 170, 92, 300
    for i, r in enumerate(top_noise):
        y = y0 + i * 24
        ratio = num(r["low_relevance_play_ratio"])
        parts.append(f'<text x="24" y="{y+14}" class="svg-small">{esc(r["project_name"][:10])}</text>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{maxw*ratio:.1f}" height="14" rx="4" fill="#ef4444" opacity="0.78"/>')
        parts.append(f'<text x="{x0+maxw*ratio+8:.1f}" y="{y+12}" class="svg-small">{ratio:.0%}</text>')
    # right manual deltas
    parts.append('<text x="540" y="70" class="svg-subtitle">人工回流确认的触达修正 / 假破圈</text>')
    if manual:
        deltas = [abs(num(r.get("manual_reach_play_delta"))) for r in manual]
        max_delta = max(deltas) if deltas else 1
        for i, r in enumerate(manual[:10]):
            y = y0 + i * 30
            delta = abs(num(r.get("manual_reach_play_delta")))
            w = 300 * delta / max_delta if max_delta else 0
            color = "#dc2626" if r.get("manual_audit_verdict") else "#f97316"
            parts.append(f'<text x="540" y="{y+15}" class="svg-small">{esc(r["project_name"][:12])}</text>')
            parts.append(f'<rect x="665" y="{y}" width="{w:.1f}" height="16" rx="4" fill="{color}" opacity="0.82"/>')
            note = r.get("manual_audit_verdict") or "row override"
            parts.append(f'<text x="{665+w+8:.1f}" y="{y+13}" class="svg-small">-{fmt_short(delta)} · {esc(note)}</text>')
    parts.append(svg_footer())
    return "\n".join(parts)


def svg_header(width: int, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<style>
.svg-title{{font:700 22px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#0f172a}}
.svg-subtitle{{font:700 15px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#334155}}
.svg-label{{font:600 14px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#334155}}
.svg-value{{font:700 14px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#0f172a}}
.svg-axis{{font:600 13px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#475569}}
.svg-small{{font:12px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#334155}}
.svg-quad-label{{font:700 13px system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#334155}}
</style>
<rect width="100%" height="100%" fill="#ffffff"/>'''


def svg_footer() -> str:
    return "</svg>"


def build_html(rows: list[dict[str, str]], quad: str, tier: str, noise: str, summary: dict[str, Any]) -> str:
    top_reach = sorted(rows, key=lambda r: num(r["likely_total_play"]), reverse=True)[:12]
    small_breakout = [r for r in rows if r["final_tier"] == "T2_small_breakout"]
    false_breakout = [r for r in rows if r["final_tier"] == "T0_false_breakout_demoted"]
    high_stock_low = [r for r in rows if r["quadrant"] == "stock_high__reach_low"]
    near_invisible = [r for r in rows if r["final_tier"].startswith("T4")]

    data_json = json.dumps(rows, ensure_ascii=False)

    def project_cards(items: list[dict[str, str]], field: str = "headline_claim", limit: int = 8) -> str:
        out = []
        for r in items[:limit]:
            out.append(f'''
<article class="project-card" data-tier="{esc(r['final_tier'])}" data-project="{esc(r['project_name'])}">
  <div class="project-top"><span class="pill" style="--c:{TIER_COLORS.get(r['final_tier'],'#64748b')}">{esc(TIER_LABELS.get(r['final_tier'], r['final_tier']))}</span><span>{esc(r['quadrant_label'])}</span></div>
  <h4>{esc(r['project_name'])}</h4>
  <p>{esc(r.get(field) or r.get('interpretation') or '')}</p>
  <dl><div><dt>相关播放</dt><dd>{fmt_short(r['likely_total_play'])}</dd></div><div><dt>存量</dt><dd>{fmt_short(r['scale_video_count_best'])}</dd></div><div><dt>低相关占比</dt><dd>{num(r['low_relevance_play_ratio']):.0%}</dd></div></dl>
</article>''')
        return "\n".join(out)

    rows_html = []
    for r in rows:
        rows_html.append(f'''
<tr data-tier="{esc(r['final_tier'])}" data-quadrant="{esc(r['quadrant'])}" data-name="{esc(r['project_name'])}">
<td>{esc(r['final_rank'])}</td><td><strong>{esc(r['project_name'])}</strong><br><span>{esc(r['category'])}</span></td>
<td>{esc(TIER_LABELS.get(r['final_tier'], r['final_tier']))}</td><td>{esc(r['quadrant_label'])}</td>
<td class="num">{fmt_short(r['scale_video_count_best'])}</td><td class="num">{fmt_short(r['likely_total_play'])}</td>
<td class="num">{num(r['low_relevance_play_ratio']):.0%}</td><td>{esc(r['manual_audit_verdict'] or '—')}</td>
<td>{esc(r['headline_claim'])}</td>
</tr>''')

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TikTok 非遗收口数据可视化 Dashboard</title>
<style>
:root {{
  --bg:#f8fafc; --ink:#0f172a; --muted:#64748b; --line:#dbe3ef; --card:#ffffff;
  --green:#1f9d7a; --blue:#3b82f6; --amber:#d88923; --red:#dc2626; --slate:#64748b;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif}}
header{{padding:34px 42px 22px;background:#0f172a;color:white}}
header h1{{margin:0 0 10px;font-size:30px;letter-spacing:-.02em}}
header p{{margin:0;color:#cbd5e1;max-width:980px}}
main{{padding:26px 42px 56px;max-width:1500px;margin:auto}}
.kpis{{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:14px;margin:0 0 20px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px;box-shadow:0 12px 35px rgba(15,23,42,.05)}}
.kpi span{{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}}
.kpi strong{{display:block;font-size:28px;margin-top:6px}}
.section{{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:20px;margin:18px 0;box-shadow:0 14px 36px rgba(15,23,42,.05)}}
.section h2{{margin:0 0 8px;font-size:21px}}
.section .note{{margin:0 0 16px;color:var(--muted)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}}
.svg-wrap{{overflow:auto;border-radius:16px;border:1px solid #edf2f7;background:white;padding:6px}}
svg{{max-width:100%;height:auto;display:block}}
.narrative-grid{{display:grid;grid-template-columns:repeat(3,minmax(260px,1fr));gap:14px}}
.narrative{{border:1px solid var(--line);border-radius:18px;padding:16px;background:#fbfdff}}
.narrative h3{{margin:0 0 8px;font-size:17px}}
.narrative p{{margin:0;color:#475569}}
.project-list{{display:grid;grid-template-columns:repeat(4,minmax(220px,1fr));gap:12px}}
.project-card{{border:1px solid var(--line);border-radius:16px;background:white;padding:13px;min-height:160px}}
.project-card h4{{margin:8px 0 6px;font-size:17px}}
.project-card p{{margin:0 0 12px;color:#475569;font-size:13px}}
.project-top{{display:flex;gap:8px;align-items:center;justify-content:space-between;color:var(--muted);font-size:12px}}
.pill{{display:inline-flex;align-items:center;border-radius:999px;padding:3px 8px;background:color-mix(in srgb,var(--c) 13%, white);color:var(--c);font-weight:700;white-space:nowrap}}
dl{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0}}dt{{font-size:11px;color:var(--muted)}}dd{{margin:0;font-weight:800}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px}}input,select{{border:1px solid var(--line);border-radius:12px;padding:9px 11px;background:white;color:var(--ink)}}
table{{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:white}}
th,td{{padding:10px 12px;border-bottom:1px solid #eef2f7;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#f8fafc;font-size:12px;color:#475569;z-index:1}}td span{{color:var(--muted);font-size:12px}}td.num{{font-variant-numeric:tabular-nums;text-align:right}}tr:last-child td{{border-bottom:none}}
.caveat{{border-left:4px solid var(--amber);background:#fffbeb;border-radius:12px;padding:12px 14px;color:#713f12}}
@media (max-width:1100px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.grid2,.narrative-grid,.project-list{{grid-template-columns:1fr}}main,header{{padding-left:18px;padding-right:18px}}}}
</style>
</head>
<body>
<header>
  <h1>TikTok 非遗收口数据可视化：从矩阵到叙事</h1>
  <p>基于人工回流后的 TikTok 收口数据。目标是内部判断“哪些结论能讲、哪些必须降噪、哪些适合转化成故事线”，不是最终展示稿。</p>
</header>
<main>
  <section class="kpis">
    <div class="kpi"><span>项目总数</span><strong>{summary['total_projects']}</strong></div>
    <div class="kpi"><span>T1 规模化候选</span><strong>{summary['t1_count']}</strong></div>
    <div class="kpi"><span>T2 小众破圈</span><strong>{summary['t2_count']}</strong></div>
    <div class="kpi"><span>人工剔除假破圈</span><strong>{summary['false_breakout_count']}</strong></div>
    <div class="kpi"><span>总 likely 播放</span><strong>{fmt_short(summary['likely_total_play_sum'])}</strong></div>
  </section>

  <section class="section">
    <h2>1. 先看结构：存量 × 相关触达矩阵</h2>
    <p class="note">气泡大小代表 TikTok 相关播放量；颜色代表最终叙事层级；黑描边代表人工确认的假破圈/强修正。</p>
    <div class="svg-wrap">{quad}</div>
  </section>

  <section class="grid2">
    <div class="section">
      <h2>2. 最终分层分布</h2>
      <p class="note">这张图用于决定报告章节结构：不是所有项目都讲，重点讲层级之间的机制差异。</p>
      <div class="svg-wrap">{tier}</div>
    </div>
    <div class="section">
      <h2>3. 噪声/假破圈是一个结论，不是瑕疵</h2>
      <p class="note">高播放不等于相关传播；人工回流剔除的假亮点可以作为方法论亮点。</p>
      <div class="svg-wrap">{noise}</div>
    </div>
  </section>

  <section class="section">
    <h2>4. 可转成叙事的五条线</h2>
    <div class="narrative-grid">
      <div class="narrative"><h3>规模化出海</h3><p>春节、太极拳等同时具备高存量与高相关触达，可作为“可见性强”的主证据，但仍只讲 visibility，不讲受众认同。</p></div>
      <div class="narrative"><h3>噪声型头部</h3><p>部分头部项目低相关播放占比高，说明平台热度会被娱乐、政治、泛文化内容稀释，需要保留噪声层。</p></div>
      <div class="narrative"><h3>小众破圈</h3><p>低存量高触达项目适合作为“非规模化但有事件/内容触发”的故事线，后续要看 top evidence 是否稳定。</p></div>
      <div class="narrative"><h3>高存量低触达</h3><p>存量不低但相关触达弱，说明社区内自循环或海外语境弱，适合解释“有内容，不一定外溢”。</p></div>
      <div class="narrative"><h3>假破圈剔除</h3><p>麦西热甫、福船、珠算等人工确认降级：这是最能体现研究严谨性的反例组。</p></div>
      <div class="narrative"><h3>近不可见长尾</h3><p>大量项目在 TikTok 上缺少稳定可见性，可作为平台偏好与非遗类型差异的背景层。</p></div>
    </div>
  </section>

  <section class="section">
    <h2>5. 重点项目卡片</h2>
    <p class="note">先用这些卡片讨论叙事主线，再决定哪些进最终报告。</p>
    <h3>Top 相关触达</h3>
    <div class="project-list">{project_cards(top_reach, limit=8)}</div>
    <h3>小众破圈 / 低存量高触达</h3>
    <div class="project-list">{project_cards(small_breakout, limit=8)}</div>
    <h3>人工剔除假破圈</h3>
    <div class="project-list">{project_cards(false_breakout, field='interpretation', limit=6)}</div>
  </section>

  <section class="section">
    <h2>6. 全项目表：筛选后看细节</h2>
    <div class="controls">
      <input id="q" placeholder="搜项目/结论" />
      <select id="tier"><option value="">全部层级</option>{''.join(f'<option value="{esc(t)}">{esc(TIER_LABELS.get(t,t))}</option>' for t in TIER_ORDER)}</select>
      <select id="quad"><option value="">全部矩阵象限</option>{''.join(f'<option value="{esc(q)}">{esc(v)}</option>' for q,v in QUAD_LABELS.items())}</select>
    </div>
    <div style="max-height:620px;overflow:auto">
      <table id="tbl"><thead><tr><th>Rank</th><th>项目</th><th>层级</th><th>象限</th><th>存量</th><th>相关播放</th><th>噪声占比</th><th>人工判定</th><th>一句话</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table>
    </div>
  </section>

  <section class="section caveat">
    <strong>解释边界：</strong>这里衡量的是 TikTok 平台可见性 / likely 触达。即便是 T1，也不能直接推出“受众认同”或“传播成功”；T0/噪声组不是失败，而是关键词平台研究必须显式处理的偏差。
  </section>
</main>
<script>
const DATA = {data_json};
const q = document.getElementById('q');
const tier = document.getElementById('tier');
const quad = document.getElementById('quad');
function filterRows() {{
  const text = q.value.trim().toLowerCase();
  const tv = tier.value;
  const qv = quad.value;
  document.querySelectorAll('#tbl tbody tr').forEach(tr => {{
    const hay = tr.innerText.toLowerCase();
    const ok = (!text || hay.includes(text)) && (!tv || tr.dataset.tier === tv) && (!qv || tr.dataset.quadrant === qv);
    tr.style.display = ok ? '' : 'none';
  }});
}}
[q,tier,quad].forEach(el => el.addEventListener('input', filterRows));
</script>
</body>
</html>'''


def main() -> int:
    rows = read_csv(FINDINGS)
    if len(rows) != 44:
        raise SystemExit(f"expected 44 finding rows, got {len(rows)}")
    rows.sort(key=lambda r: int(num(r["final_rank"])))
    summary = {
        "total_projects": len(rows),
        "t1_count": sum(1 for r in rows if r["final_tier"].startswith("T1")),
        "t2_count": sum(1 for r in rows if r["final_tier"] == "T2_small_breakout"),
        "false_breakout_count": sum(1 for r in rows if r["final_tier"] == "T0_false_breakout_demoted"),
        "t4_count": sum(1 for r in rows if r["final_tier"].startswith("T4")),
        "likely_total_play_sum": sum(num(r["likely_total_play"]) for r in rows),
        "tier_counts": dict(Counter(r["final_tier"] for r in rows)),
        "quadrant_counts": dict(Counter(r["quadrant"] for r in rows)),
        "top_reach_projects": [r["project_name"] for r in sorted(rows, key=lambda r: num(r["likely_total_play"]), reverse=True)[:10]],
    }
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    quad = quadrant_svg(rows)
    tier = tier_dist_svg(rows)
    noise = noise_svg(rows)
    QUAD_SVG.write_text(quad, encoding="utf-8")
    TIER_SVG.write_text(tier, encoding="utf-8")
    NOISE_SVG.write_text(noise, encoding="utf-8")
    OUT.write_text(build_html(rows, quad, tier, noise, summary), encoding="utf-8")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"html": str(OUT.relative_to(ROOT)), "figures": [str(QUAD_SVG.relative_to(ROOT)), str(TIER_SVG.relative_to(ROOT)), str(NOISE_SVG.relative_to(ROOT))], **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
