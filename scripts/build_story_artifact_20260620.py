#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the data-journalism story page — v3 dark-editorial + interactive.

Design brief (Cloud, 2026-06-27): the v2 read like a list of findings, looked flat,
and the opening didn't grab. v3 answers that:
  - 深色大刊 high-contrast theme (松烟墨 ground, 朱砂/石青 accents, 宋体 display).
  - Opening hook at the scale of ALL 44 items (not one project): an INTERACTIVE
    "collapse" — 44 reach bars drop from the machine-inflated number to the
    human-verified truth on a toggle. Aggregate 5.55B → 3.43B in one gesture.
  - Coherent narrative arc (海市蜃楼 → 名字 → 人工查实 → 脆弱), not a section dump.
  - Two more interactive touches: scatter hover, name-variant tabs.

Vanilla JS only, system fonts only (sandbox/CSP-safe). Degrades to readable static
HTML with JS off. Inputs/outputs unchanged from v2 (additive derived reads).
"""
from __future__ import annotations
import csv, json, math, html
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data/derived"
RL = ROOT / "data/final/tiktok_closed_20260619/row_labels/tiktok_video_relevance_labels_final.ndjson"
OUT = ROOT / "docs/story_artifact_20260620.html"                       # Artifact body-content 版
STANDALONE = ROOT / "docs/中国非遗海外能见度_数据故事_20260620.html"      # 完整独立可分发版

# dark editorial palette
PAPER="#15120D"; BG2="#1C1810"; CARD="#231D14"; INK="#ECE3D0"; SUB="#9F9580"
CINN="#DA512F"; TEAL="#48A89C"; GREY="#6B6353"; LINE="#3A3227"; GOLD="#CB9C46"

def esc(s): return html.escape(str(s if s is not None else ""), quote=True)
def pint(v):
    try: return int(float(str(v).replace(",",""))) if v not in (None,"") else 0
    except: return 0
def pf(v):
    try: return float(v)
    except: return 0.0
def short(n):
    n=float(n)
    if n>=1e9: return f"{n/1e9:.2f}B"
    if n>=1e6: return f"{n/1e6:.0f}M"
    if n>=1e3: return f"{n/1e3:.0f}K"
    return str(int(n))
def short_cn(n):
    n=float(n)
    if n>=1e8: return f"{n/1e8:.2f}亿"
    if n>=1e4: return f"{n/1e4:.0f}万"
    return str(int(n))
def lg(v): return math.log10(max(float(v),1.0))

# ---------------- data
def load():
    comp=json.loads((D/"tiktok_china_signal_filtered_reach_comparison_20260620.json").read_text("utf-8"))
    auth={r["project_name"]:r for r in csv.DictReader((D/"tiktok_author_concentration_20260620.csv").open(encoding="utf-8-sig"))}
    xp=json.loads((D/"cross_platform_visibility_matrix_20260620.json").read_text("utf-8"))
    af=D/"tiktok_head_check_reach_corrected_20260620.json"
    anchor={int(r["project_id"]):r for r in json.loads(af.read_text("utf-8"))} if af.exists() else {}
    sf=D/"tiktok_head_check_summary_20260620.json"
    hsum=json.loads(sf.read_text("utf-8")) if sf.exists() else {}
    return comp, auth, xp, anchor, hsum

def naming_terms():
    """no-signal ratio per (project, term) on likely pool, for the naming figure."""
    want={"中国水密隔舱福船制造技艺":["junk","watertight","fuchuan"],
          "中国书法":["calligraphy","shufa","chineseink"],
          "中国剪纸":["papercut","papercutting","chinesepapercut"],
          "中国珠算":["abacus","zhusuan"],
          "龙泉青瓷传统烧制技艺":["celadon","longquanceladon"]}
    agg=defaultdict(lambda:{"n":0,"nosig":0})
    with RL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d=json.loads(line)
            if d.get("quality_label")!="likely_relevant": continue
            t=(d.get("source_term") or "").strip(); p=d.get("project_name","")
            a=agg[(p,t)]; a["n"]+=1
            if not (bool(d.get("china_context_hit")) or bool(d.get("has_cjk_desc"))): a["nosig"]+=1
    out=[]
    for proj,terms in want.items():
        row=[]
        for t in terms:
            a=agg.get((proj,t))
            if a and a["n"]>=10:
                row.append((t, a["nosig"]/a["n"], a["n"]))
        if row: out.append((proj,row))
    return out

# ---------------- svg helpers
def svg(w,h,body): return (f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet" '
    f'font-family=\'"PingFang SC","Microsoft YaHei",system-ui,sans-serif\' role="img">'
    f'<rect width="{w}" height="{h}" fill="{CARD}"/>{body}</svg>')

def fig_scatter(comp, anchor=None):
    anchor=anchor or {}
    W,H=920,600; ML,MR,MT,MB=64,24,54,64; PW,PH=W-ML-MR,H-MT-MB
    pts=[]
    for c in comp:
        st=pint(c.get("scale_video_count_best")); raw=pint(c.get("before_likely_total_play")); fi=pint(c.get("signal_likely_total_play"))
        if st<=0 and raw<=0: continue
        a=anchor.get(int(c["project_id"]))
        anc=pint(a.get("reach_human_anchored")) if a and pint(a.get("head_false_kill_play"))>0 else 0
        pts.append((c.get("project_name",""),st,raw,fi,c.get("signal_quadrant",""),anc))
    xs=[lg(p[1]) for p in pts]; ys=[lg(max(p[2],1)) for p in pts]+[lg(max(p[3],1)) for p in pts]
    x0,x1=min(xs)-.2,max(xs)+.2; y0,y1=min(ys)-.3,max(ys)+.3
    xm=median([lg(p[1]) for p in pts]); ym=median([lg(max(p[3],1)) for p in pts])
    X=lambda v: ML+(v-x0)/(x1-x0)*PW; Y=lambda v: MT+PH-(v-y0)/(y1-y0)*PH
    b=[]
    qx,qy=X(xm),Y(ym)
    b.append(f'<rect x="{qx}" y="{MT}" width="{ML+PW-qx}" height="{qy-MT}" fill="{TEAL}" opacity="0.10"/>')
    b.append(f'<rect x="{ML}" y="{qy}" width="{qx-ML}" height="{MT+PH-qy}" fill="{GREY}" opacity="0.16"/>')
    b.append(f'<rect x="{qx}" y="{qy}" width="{ML+PW-qx}" height="{MT+PH-qy}" fill="{CINN}" opacity="0.10"/>')
    for e in range(int(math.floor(y0)),int(math.ceil(y1))+1):
        yy=Y(e)
        if MT<=yy<=MT+PH: b.append(f'<text x="{ML-8}" y="{yy+4}" text-anchor="end" font-size="10" fill="{SUB}">{short(10**e)}</text>')
    for e in range(int(math.floor(x0)),int(math.ceil(x1))+1):
        xx=X(e)
        if ML<=xx<=ML+PW: b.append(f'<text x="{xx}" y="{MT+PH+16}" text-anchor="middle" font-size="10" fill="{SUB}">{short(10**e)}</text>')
    b.append(f'<line x1="{qx}" y1="{MT}" x2="{qx}" y2="{MT+PH}" stroke="{LINE}" stroke-dasharray="3 4"/>')
    b.append(f'<line x1="{ML}" y1="{qy}" x2="{ML+PW}" y2="{qy}" stroke="{LINE}" stroke-dasharray="3 4"/>')
    b.append(f'<text x="{ML+PW-6}" y="{MT+15}" text-anchor="end" font-size="11" fill="{TEAL}" font-weight="700">真·规模化出海</text>')
    b.append(f'<text x="{ML+6}" y="{MT+15}" font-size="11" fill="{SUB}" font-weight="700">小而精破圈</text>')
    b.append(f'<text x="{ML+PW-6}" y="{MT+PH-8}" text-anchor="end" font-size="11" fill="{CINN}" font-weight="700">高存量·低触达·自循环</text>')
    b.append(f'<text x="{ML+6}" y="{MT+PH-8}" font-size="11" fill="{GREY}" font-weight="700">近乎隐形</text>')
    for nm,st,raw,fi,q,anc in pts:
        x=X(lg(st)); yr=Y(lg(max(raw,1))); yf=Y(lg(max(fi,1)))
        tip=f'{nm}\n真实触达 {short(anc if anc>fi else fi)}（机器口径 {short(raw)}）'
        b.append(f'<g class="pt"><title>{esc(tip)}</title>')
        b.append(f'<line x1="{x:.1f}" y1="{yr:.1f}" x2="{x:.1f}" y2="{yf:.1f}" stroke="{GREY}" stroke-width="1.3" opacity="0.6"/>')
        b.append(f'<circle cx="{x:.1f}" cy="{yr:.1f}" r="2.2" fill="{GREY}"/>')
        if anc>fi:
            ya=Y(lg(max(anc,1)))
            b.append(f'<path d="M {x:.1f} {ya-4:.1f} L {x+4:.1f} {ya:.1f} L {x:.1f} {ya+4:.1f} L {x-4:.1f} {ya:.1f} Z" fill="{TEAL}" stroke="{CARD}" stroke-width="0.6"/>')
        b.append(f'<circle class="dot" cx="{x:.1f}" cy="{yf:.1f}" r="3.4" fill="{CINN}"/>')
        b.append(f'<text class="lbl" x="{x+5:.1f}" y="{yf-4:.1f}" font-size="8.5" fill="{INK}">{esc(nm)}</text></g>')
    b.append(f'<text x="{ML+PW/2}" y="{H-20}" text-anchor="middle" font-size="11" fill="{SUB}">存量（话题视频规模，对数）→</text>')
    b.append(f'<text x="16" y="{MT+PH/2}" text-anchor="middle" font-size="11" fill="{SUB}" transform="rotate(-90 16 {MT+PH/2})">触达（相关播放，对数）→</text>')
    b.append(f'<circle cx="{ML+8}" cy="{MT+PH-54}" r="2.2" fill="{GREY}"/><text x="{ML+16}" y="{MT+PH-50}" font-size="9.5" fill="{INK}">上界·机器likely（含撞词）</text>')
    b.append(f'<path d="M {ML+8} {MT+PH-42} l 4 4 l -4 4 l -4 -4 Z" fill="{TEAL}"/><text x="{ML+16}" y="{MT+PH-34}" font-size="9.5" fill="{INK}">人工锚定·头部378条核查真值</text>')
    b.append(f'<circle cx="{ML+8}" cy="{MT+PH-22}" r="3.4" fill="{CINN}"/><text x="{ML+16}" y="{MT+PH-18}" font-size="9.5" fill="{INK}">下界·中国信号过滤</text>')
    return svg(W,H,"".join(b))

def fig_dumbbell(comp):
    rows=[c for c in comp if pint(c.get("before_likely_total_play"))>0]
    rows.sort(key=lambda c: pf(c.get("play_drop_ratio")), reverse=True)
    n=len(rows); rh=14; MT,MB,ML,MR=40,30,180,86; PH=n*rh; H=MT+PH+MB; W=900; PW=W-ML-MR
    pl=[pint(c["before_likely_total_play"]) for c in rows]+[max(pint(c["signal_likely_total_play"]),1) for c in rows]
    lo,hi=lg(min(pl))-.2,lg(max(pl))+.2; X=lambda v: ML+(lg(max(v,1))-lo)/(hi-lo)*PW
    b=[]
    for e in range(int(math.floor(lo)),int(math.ceil(hi))+1):
        xx=X(10**e)
        if ML<=xx<=ML+PW: b.append(f'<line x1="{xx}" y1="{MT}" x2="{xx}" y2="{MT+PH}" stroke="{LINE}" opacity="0.6"/><text x="{xx}" y="{MT-6}" text-anchor="middle" font-size="9" fill="{SUB}">{short(10**e)}</text>')
    for i,c in enumerate(rows):
        y=MT+i*rh+rh/2; raw=pint(c["before_likely_total_play"]); fi=pint(c["signal_likely_total_play"]); dr=pf(c["play_drop_ratio"])
        col=CINN if dr>=.7 else (GOLD if dr>=.4 else TEAL)
        b.append(f'<text x="{ML-8}" y="{y+3}" text-anchor="end" font-size="9.5" fill="{INK}">{esc(c["project_name"])}</text>')
        b.append(f'<line x1="{X(fi):.1f}" y1="{y:.1f}" x2="{X(raw):.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="2" opacity="0.55"/>')
        b.append(f'<circle cx="{X(fi):.1f}" cy="{y:.1f}" r="3" fill="{INK}"/><circle cx="{X(raw):.1f}" cy="{y:.1f}" r="3" fill="{col}"/>')
        b.append(f'<text x="{ML+PW+8}" y="{y+3}" font-size="8.5" fill="{col}">−{dr*100:.0f}%</text>')
    b.append(f'<circle cx="{ML}" cy="{MT+PH+20}" r="3" fill="{INK}"/><text x="{ML+9}" y="{MT+PH+24}" font-size="9.5" fill="{INK}">过滤后·下界</text>')
    b.append(f'<circle cx="{ML+120}" cy="{MT+PH+20}" r="3" fill="{CINN}"/><text x="{ML+129}" y="{MT+PH+24}" font-size="9.5" fill="{INK}">机器likely·上界</text>')
    return svg(W,H,"".join(b))

def fig_author(auth):
    rows=[r for r in auth.values() if pint(r["n_signal_videos"])>0]
    rows.sort(key=lambda r:pf(r["top1_author_share"]), reverse=True)
    n=len(rows); rh=15; MT,MB,ML,MR=40,24,170,150; PH=n*rh; H=MT+PH+MB; W=880; PW=W-ML-MR
    b=[]
    for frac in (0,.25,.5,.75,1):
        xx=ML+frac*PW; b.append(f'<line x1="{xx}" y1="{MT}" x2="{xx}" y2="{MT+PH}" stroke="{LINE}" opacity="0.6"/><text x="{xx}" y="{MT-6}" text-anchor="middle" font-size="9" fill="{SUB}">{int(frac*100)}%</text>')
    for i,r in enumerate(rows):
        y=MT+i*rh; s=pf(r["top1_author_share"]); c=CINN if s>=.5 else (GOLD if s>=.25 else TEAL); bw=s*PW
        b.append(f'<text x="{ML-8}" y="{y+11}" text-anchor="end" font-size="9.5" fill="{INK}">{esc(r["project_name"])}</text>')
        b.append(f'<rect x="{ML}" y="{y+3}" width="{bw:.1f}" height="{rh-6}" rx="2" fill="{c}" opacity="0.92"/>')
        b.append(f'<text x="{ML+bw+6:.1f}" y="{y+11}" font-size="8.5" fill="{SUB}">{s*100:.0f}% · {esc(r["n_signal_videos"])}视频/{esc(r["n_signal_authors"])}号</text>')
    b.append(f'<rect x="{ML}" y="{MT+PH+6}" width="11" height="11" rx="2" fill="{CINN}"/><text x="{ML+15}" y="{MT+PH+15}" font-size="9.5" fill="{INK}">≥50% 单一博主独撑（脆弱）</text>')
    b.append(f'<rect x="{ML+220}" y="{MT+PH+6}" width="11" height="11" rx="2" fill="{TEAL}"/><text x="{ML+235}" y="{MT+PH+15}" font-size="9.5" fill="{INK}">&lt;25% 去中心化扩散（稳健）</text>')
    return svg(W,H,"".join(b))

# ---------------- html building blocks
def seal(label):
    return (f'<span class="seal"><svg viewBox="0 0 40 40" width="40" height="40">'
            f'<rect x="1.5" y="1.5" width="37" height="37" rx="4" fill="{CINN}"/>'
            f'<rect x="4.5" y="4.5" width="31" height="31" rx="2" fill="none" stroke="{PAPER}" stroke-width="1" opacity="0.5"/>'
            f'<text x="20" y="25" text-anchor="middle" font-size="17" fill="#F6EFE0" '
            f'font-family=\'"Songti SC","SimSun",serif\' font-weight="700">{esc(label)}</text></svg></span>')

NAME_TYPE={"junk":("英译泛词","grey"),"watertight":("英译泛词","grey"),"calligraphy":("英译泛词","grey"),
    "papercut":("英译泛词","grey"),"papercutting":("英译泛词","grey"),"abacus":("英译泛词","grey"),"celadon":("英译泛词","grey"),
    "fuchuan":("拼音专名","cinn"),"shufa":("拼音专名","cinn"),"zhusuan":("拼音专名","cinn"),"longquanceladon":("拼音专名","cinn"),
    "chineseink":("Chinese+ 限定","teal"),"chinesepapercut":("Chinese+ 限定","teal")}
NAME_DISPLAY={"中国水密隔舱福船制造技艺":"福船","中国书法":"书法","中国剪纸":"剪纸","中国珠算":"珠算","龙泉青瓷传统烧制技艺":"龙泉青瓷"}

def naming_html(data):
    tabs=[]; panels=[]
    for i,(proj,terms) in enumerate(data):
        disp=NAME_DISPLAY.get(proj,proj)
        act="active" if i==0 else ""
        tabs.append(f'<button class="nmtab {act}" data-i="{i}">{esc(disp)}</button>')
        rows=[]
        for t,r,n in sorted(terms,key=lambda x:-x[1]):
            typ,ck=NAME_TYPE.get(t,("",""))
            cls={"grey":"g","cinn":"c","teal":"t"}.get(ck,"g")
            rows.append(
                f'<div class="nmrow"><div class="nmterm mono">{esc(t)}</div>'
                f'<div class="nmtrack"><div class="nmbar {cls}" style="width:{r*100:.0f}%"></div></div>'
                f'<div class="nmval {cls}">{r*100:.0f}% 撞词 · {esc(typ)}</div></div>')
        panels.append(f'<div class="nmpanel {act}" data-i="{i}">{"".join(rows)}</div>')
    return f'<div class="nmtabs">{"".join(tabs)}</div><div class="nmpanels">{"".join(panels)}</div>'

def xp_table(xp):
    order=["both_visible","tiktok_led","both_low"]
    lab={"both_visible":"双平台可见","tiktok_led":"TikTok 主导","both_low":"双平台均低"}
    comp=[r for r in xp if r["yt_status"]=="collected"]
    by=defaultdict(list)
    for r in comp: by[r["cross_platform_pattern"]].append(r)
    out=['<table class="xp"><thead><tr><th>项目</th><th>模式</th><th>TikTok 触达区间</th><th>YouTube 触达区间</th></tr></thead><tbody>']
    for k in order:
        for r in sorted(by.get(k,[]),key=lambda x:-pint(x["tt_reach_upper_raw"])):
            tt=f'{short(r["tt_reach_lower_signal"])}–{short(r["tt_reach_upper_raw"])}'
            yt=f'{short(r["yt_reach_lower_likely"])}–{short(r["yt_reach_upper_inclusive"])}'
            out.append(f'<tr><td>{esc(r["project_name"])}</td><td><span class="pat {k}">{lab[k]}</span></td>'
                       f'<td class="mono">{tt}</td><td class="mono">{yt}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)

# ---------------- CSS (plain string; dark editorial) ----------------
CSS = """<style>
 *{box-sizing:border-box}
 .pg{background:#15120D;color:#ECE3D0;margin:0;
   font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;line-height:1.75;
   -webkit-font-smoothing:antialiased}
 .wrap{max-width:1060px;margin:0 auto;padding:0 24px}
 .serif{font-family:"Songti SC","Source Han Serif SC","Noto Serif CJK SC","SimSun",serif}
 .mono{font-family:ui-monospace,"SF Mono","Cascadia Code",Consolas,monospace;font-variant-numeric:tabular-nums}
 /* hero */
 .hero{min-height:100vh;display:flex;flex-direction:column;justify-content:center;
   padding:64px 0 48px;position:relative;border-bottom:1px solid #3A3227}
 .eyebrow{font-size:12px;letter-spacing:.36em;color:#DA512F;font-weight:700;margin:0 0 22px}
 h1.title{font-size:clamp(38px,7.6vw,88px);line-height:1.08;margin:0 0 24px;font-weight:700;letter-spacing:.005em}
 h1.title em{font-style:normal;color:#DA512F}
 .lede{font-size:clamp(15px,2vw,19px);color:#BFB6A0;max-width:62ch;margin:0 0 8px}
 /* collapse widget */
 .collapse{margin:40px 0 0}
 .cphead{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;margin-bottom:6px}
 .cpbig{font-family:"Songti SC","SimSun",serif;font-size:clamp(40px,8vw,76px);line-height:1;color:#DA512F;font-weight:700}
 .cpbig.t{color:#48A89C}
 .cplab{font-size:13px;color:#9F9580;letter-spacing:.04em}
 .cpsub{font-size:13.5px;color:#BFB6A0;margin:2px 0 16px}
 .bars{display:flex;align-items:flex-end;gap:3px;height:240px;padding:0 0 2px;
   border-bottom:1px solid #3A3227;overflow:hidden}
 .bar{flex:1 1 0;min-width:0;position:relative;height:100%;display:flex;align-items:flex-end;cursor:default}
 .ghost{position:absolute;left:0;right:0;bottom:0;background:repeating-linear-gradient(180deg,rgba(218,81,47,.16),rgba(218,81,47,.16) 2px,transparent 2px,transparent 4px);border-top:1px dotted rgba(218,81,47,.5)}
 .fill{position:relative;width:100%;background:linear-gradient(180deg,#DA512F,#a83b20);border-radius:1px 1px 0 0;
   height:0;transition:height 1.05s cubic-bezier(.4,.7,.2,1)}
 .bar.rise .fill{background:linear-gradient(180deg,#48A89C,#2f7a70)}
 .bar:hover .fill{filter:brightness(1.2)}
 .bar .tip{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);white-space:nowrap;
   background:#231D14;border:1px solid #3A3227;color:#ECE3D0;font-size:11px;padding:4px 8px;border-radius:5px;
   opacity:0;pointer-events:none;transition:opacity .15s;margin-bottom:4px;z-index:5}
 .bar:hover .tip{opacity:1}
 .barleg{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:12px;color:#9F9580}
 .barleg span{display:inline-flex;align-items:center;gap:6px}
 .barleg .sw{width:12px;height:12px;border-radius:2px;display:inline-block}
 .barleg .sw.c{background:#DA512F} .barleg .sw.t{background:#48A89C}
 .barleg .sw.gh{background:transparent;border-top:2px dotted rgba(218,81,47,.7);height:0;width:14px;border-radius:0}
 .cpctl{display:flex;align-items:center;gap:14px;margin-top:18px;flex-wrap:wrap}
 .toggle{appearance:none;border:1px solid #DA512F;background:transparent;color:#ECE3D0;
   font:inherit;font-size:14px;padding:9px 20px;border-radius:30px;cursor:pointer;transition:.2s;font-weight:600}
 .toggle:hover{background:rgba(218,81,47,.14)}
 .cphint{font-size:12.5px;color:#9F9580}
 /* sections */
 section{padding:68px 0;border-bottom:1px solid #3A3227}
 section.alt{background:#1C1810}
 .sec-h{display:flex;align-items:center;gap:14px;margin:0 0 6px}
 .seal{flex:0 0 auto;line-height:0}
 h2{font-size:clamp(23px,3.4vw,36px);margin:0;font-weight:700;line-height:1.2}
 .kicker{font-size:11.5px;letter-spacing:.24em;color:#48A89C;font-weight:700;margin:0 0 4px}
 .lead{font-size:16px;color:#BFB6A0;max-width:68ch;margin:10px 0 24px}
 .lead b,.note b,.card b{color:#ECE3D0}
 .fig{background:#231D14;border:1px solid #3A3227;border-radius:12px;padding:16px;margin:20px 0;overflow:visible;position:relative}
 .fig svg{display:block}
 .fig .pt .lbl{opacity:.62;transition:.15s} .fig .pt:hover .lbl{opacity:1;font-weight:700}
 .fig .pt:hover .dot{r:5.4}
 .cap{font-size:12.5px;color:#9F9580;margin:8px 2px 0}
 .pull{font-family:"Songti SC","SimSun",serif;font-size:clamp(21px,3.2vw,32px);line-height:1.45;
   color:#ECE3D0;margin:30px 0;max-width:24ch}
 .pull .hl{color:#DA512F}
 /* full-bleed quote band */
 .band{background:#DA512F;color:#1A140F;padding:60px 0;margin:0;border:0}
 .band .q{font-family:"Songti SC","SimSun",serif;font-size:clamp(24px,4vw,44px);line-height:1.3;font-weight:700;max-width:20ch;margin:0}
 .band .a{font-size:14px;margin-top:16px;color:#4a1f12}
 /* tables / tags */
 table{border-collapse:collapse;width:100%;font-size:13px;background:#231D14}
 th,td{border-bottom:1px solid #3A3227;padding:8px 11px;text-align:left}
 th{color:#9F9580;font-weight:600;font-size:12px;letter-spacing:.04em}
 td.mono{text-align:right}
 .pat{font-size:11.5px;padding:2px 9px;border-radius:20px;color:#15120D;font-weight:700}
 .pat.both_visible{background:#48A89C} .pat.tiktok_led{background:#DA512F} .pat.both_low{background:#6B6353}
 /* cards / grid */
 .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
 .note{background:#211A11;border:1px solid #4a3a1f;border-left:3px solid #CB9C46;border-radius:8px;padding:14px 16px;font-size:13.5px;color:#cdbf9d;margin:16px 0}
 .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:20px}
 .card{background:#231D14;border:1px solid #3A3227;border-radius:12px;padding:17px 18px}
 .card h3{margin:0 0 7px;font-size:15.5px}
 .card p{margin:0;font-size:13px;color:#A99F88;line-height:1.65}
 .card.big{grid-column:span 1}
 .stat b{font-family:"Songti SC","SimSun",serif;font-size:clamp(28px,4vw,42px);color:#DA512F;display:block;line-height:1}
 .stat.t b{color:#48A89C}
 .stat span{font-size:12.5px;color:#9F9580}
 /* naming interactive */
 .nmtabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px}
 .nmtab{appearance:none;border:1px solid #3A3227;background:#231D14;color:#A99F88;font:inherit;font-size:13.5px;
   padding:7px 16px;border-radius:24px;cursor:pointer;transition:.18s}
 .nmtab:hover{border-color:#DA512F;color:#ECE3D0}
 .nmtab.active{background:#DA512F;border-color:#DA512F;color:#15120D;font-weight:700}
 .nmpanel{display:none;padding:12px 2px 4px}
 .nmpanel.active{display:block;animation:fade .4s ease both}
 .nmrow{display:grid;grid-template-columns:120px 1fr auto;align-items:center;gap:12px;margin:9px 0}
 .nmterm{font-size:13px;color:#BFB6A0;text-align:right}
 .nmtrack{background:#1A150E;border-radius:4px;height:22px;overflow:hidden}
 .nmbar{height:100%;border-radius:4px;transition:width 1s cubic-bezier(.4,.7,.2,1)}
 .nmbar.g{background:#6B6353} .nmbar.c{background:#DA512F} .nmbar.t{background:#48A89C}
 .nmval{font-size:12.5px;font-weight:700;white-space:nowrap}
 .nmval.g{color:#9F9580} .nmval.c{color:#DA512F} .nmval.t{color:#48A89C}
 footer{padding:46px 0 80px;color:#9F9580;font-size:12.5px}
 @keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
 @media(max-width:680px){.grid2{grid-template-columns:1fr}.nmrow{grid-template-columns:84px 1fr;}.nmval{grid-column:2}.bars{height:180px}}
 @media(prefers-reduced-motion:no-preference){.hero>.wrap>*{animation:rise .7s cubic-bezier(.2,.7,.3,1) both}
   .hero .title{animation-delay:.05s}.hero .lede{animation-delay:.12s}.hero .collapse{animation-delay:.2s}}
 @keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
</style>"""

# ---------------- JS (plain string; DATA injected) ----------------
JS = """<script>
(function(){
 var DATA = /*DATA*/;
 var bars=document.getElementById('bars');
 if(bars){
   var vals=[]; DATA.forEach(function(d){vals.push(d.m); vals.push(Math.max(d.a,1));});
   var dmin=Math.log10(Math.max(Math.min.apply(null,vals),1))-0.15;
   var dmax=Math.log10(Math.max.apply(null,vals))+0.05;
   function hpx(v){var t=(Math.log10(Math.max(v,1))-dmin)/(dmax-dmin);return Math.max(t*100,1.2);}
   DATA.forEach(function(d){
     var bar=document.createElement('div'); bar.className='bar'+(d.a>d.f?' rise':'');
     var gh=document.createElement('div'); gh.className='ghost'; gh.style.height=hpx(d.m)+'%';
     var fl=document.createElement('div'); fl.className='fill'; fl.setAttribute('data-m',hpx(d.m)); fl.setAttribute('data-a',hpx(d.a));
     var tip=document.createElement('div'); tip.className='tip';
     tip.textContent=d.n+' · 真实 '+d.cn_a+'（机器 '+d.cn_m+'）';
     bar.appendChild(gh); bar.appendChild(fl); bar.appendChild(tip); bars.appendChild(bar);
   });
   var state='truth';
   var totM=0,totA=0; DATA.forEach(function(d){totM+=d.m; totA+=d.a;});
   var big=document.getElementById('cpbig'), lab=document.getElementById('cplab'), btn=document.getElementById('cptoggle');
   function cn(v){return v>=1e8?(v/1e8).toFixed(2)+'亿':(v/1e4).toFixed(0)+'万';}
   var shown=totM;
   function countTo(target){
     var start=shown, t0=null, dur=900;
     function step(ts){if(!t0)t0=ts; var p=Math.min((ts-t0)/dur,1); var e=1-Math.pow(1-p,3);
       shown=start+(target-start)*e; big.textContent=cn(shown); if(p<1)requestAnimationFrame(step);}
     requestAnimationFrame(step);
     setTimeout(function(){shown=target; big.textContent=cn(target);}, dur+80); // guarantee final value
   }
   function apply(st){
     state=st;
     var fills=bars.querySelectorAll('.fill');
     for(var i=0;i<fills.length;i++){fills[i].style.height=fills[i].getAttribute(st==='truth'?'data-a':'data-m')+'%';}
     if(st==='truth'){big.className='cpbig t'; lab.textContent='人工查实的真实触达'; countTo(totA); btn.textContent='▸ 看机器以为的';}
     else{big.className='cpbig'; lab.textContent='机器口径“看起来”的触达'; countTo(totM); btn.textContent='◂ 收回真相';}
   }
   btn.addEventListener('click',function(){apply(state==='truth'?'machine':'truth');});
   // entrance: show machine, then collapse to truth
   shown=totM; big.textContent=cn(totM); big.className='cpbig'; lab.textContent='机器口径“看起来”的触达';
   var fills=bars.querySelectorAll('.fill'); for(var i=0;i<fills.length;i++){fills[i].style.height=fills[i].getAttribute('data-m')+'%';}
   setTimeout(function(){apply('truth');},900);
 }
 // naming tabs
 var tabs=document.querySelectorAll('.nmtab');
 tabs.forEach(function(tb){tb.addEventListener('click',function(){
   var i=tb.getAttribute('data-i');
   document.querySelectorAll('.nmtab').forEach(function(x){x.classList.toggle('active',x.getAttribute('data-i')===i);});
   document.querySelectorAll('.nmpanel').forEach(function(x){x.classList.toggle('active',x.getAttribute('data-i')===i);});
 });});
})();
</script>"""

def main():
    comp,auth,xp,anchor,hsum=load()
    name=naming_terms()
    f_sc=fig_scatter(comp,anchor); f_db=fig_dumbbell(comp); f_au=fig_author(auth)
    nm_html=naming_html(name)
    # hero collapse data (all 44, machine -> human-anchored truth)
    items=[]
    for c in comp:
        pid=int(c["project_id"]); m=pint(c.get("before_likely_total_play")); fl=pint(c.get("signal_likely_total_play"))
        a=anchor.get(pid); anc=pint(a.get("reach_human_anchored")) if a else fl
        if m<=0 and anc<=0: continue
        items.append({"n":NAME_DISPLAY.get(c["project_name"],c["project_name"]),"m":m,"a":anc,"f":fl,
                      "cn_m":short_cn(m),"cn_a":short_cn(anc)})
    items.sort(key=lambda d:d["m"],reverse=True)
    tot_m=sum(d["m"] for d in items); tot_a=sum(d["a"] for d in items)
    shrink=int((1-tot_a/tot_m)*100) if tot_m else 0
    n_collapse=sum(1 for d in items if d["m"]>0 and (d["m"]-d["a"])/d["m"]>=0.6)
    n_invis=sum(1 for d in items if d["a"]<1e6)
    js=JS.replace("/*DATA*/", json.dumps(items, ensure_ascii=False))
    # headline numbers
    fuchuan=next((t for p,ts in name for t in ts if t[0]=="fuchuan"),None)
    junk=next((t for p,ts in name for t in ts if t[0]=="junk"),None)
    fc_r=f"{fuchuan[1]*100:.0f}" if fuchuan else "45"; jk_r=f"{junk[1]*100:.0f}" if junk else "99"
    n_hi=sum(1 for c in comp if pf(c.get("play_drop_ratio"))>=0.6)
    fk=hsum.get("filter_false_kill",{}); cn=hsum.get("filter_confirmed_noise",{}); an=hsum.get("false_kill_anatomy",{})
    hc_reviewed=hsum.get("reviewed_videos",0)
    hc_noise_pct=int(cn.get("play_ratio_of_reviewed",0)*100); hc_fk_pct=int(fk.get("play_ratio_of_reviewed",0)*100)

    title="看见与看不见：中国非遗的海外能见度"
    body=f"""<div class="pg">

<header class="hero"><div class="wrap">
 <p class="eyebrow">数据新闻 · TikTok × YouTube · 44 项 UNESCO 中国非遗</p>
 <h1 class="title serif">很多非遗的“出海”，<br>是一场<em>海市蜃楼</em>。</h1>
 <p class="lede">我们把中国 44 项联合国非物质文化遗产在海外短视频上的能见度，逐项量化。
 机器口径下，它们加起来有 {short_cn(tot_m)} 次播放——看起来热闹。可只要逐条看清楚，
 其中很大一部分根本不是它：是同名异物的撞词噪声。下面这一排，是 44 项各自的“触达”。
 <b>点一下，看它在真相面前塌下去。</b></p>

 <div class="collapse">
  <div class="cphead">
   <span id="cpbig" class="cpbig" data-v="0">{short_cn(tot_m)}</span>
   <span id="cplab" class="cplab">机器口径“看起来”的触达</span>
  </div>
  <div class="cpsub">44 项中国非遗 TikTok 触达总量 · 每一根是一项</div>
  <div id="bars" class="bars" aria-hidden="true"></div>
  <div class="barleg">
   <span><i class="sw c"></i>机器高估、塌缩</span>
   <span><i class="sw t"></i>人工核查反而上修</span>
   <span><i class="sw gh"></i>虚线＝机器原本声称的高度</span>
  </div>
  <noscript><p class="cphint">（启用 JavaScript 可看交互塌缩动画。）机器口径 {short_cn(tot_m)} → 人工查实 {short_cn(tot_a)}。</p></noscript>
  <div class="cpctl">
   <button id="cptoggle" class="toggle">▸ 看机器以为的</button>
   <span class="cphint">蒸发掉的 {shrink}% 是撞词噪声；{n_collapse} 项塌掉一大半，{n_invis} 项真实触达不足百万——几乎隐形。</span>
  </div>
 </div>
</div></header>

<section><div class="wrap">
 <div class="sec-h">{seal("地图")}<div><p class="kicker">全局 · 假设一 / 假设二</p><h2 class="serif">谁被看见，谁是幽灵</h2></div></div>
 <p class="lead">横轴是该非遗在平台上的“存量规模”，纵轴是带中国身份的真实触达。每个点拖一条竖线——
 下端是中国信号过滤后的下界，上端是机器宽口径上界，<b>线越长，身份被稀释得越狠</b>。
 可被“功能化”的春节、太极、京剧落在右上；地方戏曲与濒危技艺沉向左下的隐形区。<span style="color:#9F9580">（鼠标悬停可看每项数字。）</span></p>
 <div class="fig">{f_sc}</div>
 <p class="cap">触达取区间：下界=中国信号过滤，上界=机器 likely（含撞词噪声），石青菱形=头部人工核查后的真值锚点。象限按中位线划分。</p>
</div></section>

<section class="alt"><div class="wrap">
 <div class="sec-h">{seal("蜃楼")}<div><p class="kicker">假设三 · 原创发现</p><h2 class="serif">两种“隐形”，病因相反</h2></div></div>
 <p class="lead">同样是看不见，机制完全不同。<b>被淹没型</b>：搜得到一大堆，但几乎全是同名异物——
 福船 1.84 亿播放，拆开看真身只剩 10 万。<b>缺席型</b>：本就没什么内容（侗族大歌、花儿）。
 下图按缩水比例排序，红色长条即被噪声淹没最重的项目。</p>
 <div class="fig">{f_db}</div>
 <p class="cap">每行：左点=过滤后下界，右点=机器上界；右侧百分比=触达缩水比例（≈撞词噪声占比）。</p>
</div></section>

<div class="band"><div class="wrap">
 <p class="q serif">“近乎隐形”不是一个数字，<br>而是两个：搜得到多少，<br>和搜到的里有多少<span style="text-decoration:underline">真是它</span>。</p>
 <p class="a">— 本研究对“能见度”的重新定义</p>
</div></div>

<section><div class="wrap">
 <div class="sec-h">{seal("名字")}<div><p class="kicker">核心发现 · 出海策略</p><h2 class="serif">决定它会不会被稀释的，是名字</h2></div></div>
 <p class="lead">在同一个非遗内部比较不同名称（项目不变，只变“名字怎么取”）：翻成英文泛词的撞词噪声最高，
 拼音专名次之，加 “Chinese” 限定几乎归零。福船译成 <span class="mono">junk</span> 搜出来 {jk_r}% 是无关内容，
 而 <span class="mono">fuchuan</span> 只剩 {fc_r}%。<b>点下面的名字切换不同非遗看。</b></p>
 <div class="fig">{nm_html}</div>
 <p class="cap">撞词率 = likely 视频中“无任何中国信号”的占比；同项目内对比，控制了项目本身。</p>
 <p class="pull">在 TikTok，内容是被<span class="hl">刷到</span>的。<br>保留中国名词，是让人刷到那一刻<br>一眼认出“这是中国的”。</p>
 <p class="lead">一个译成 <span class="mono">junk</span> 的福船视频，刷到的人只当是“一条旧木船”；标着 <span class="mono">fuchuan</span>、带中国语境的，才会让人记住“fuchuan”这个词。
 词被越多人认得，才可能长成一个全球通用、一眼即知出处的标签。<span style="color:#9F9580">（这一步是顺着推荐机制推断的出海策略，非本数据实测。）</span></p>
 <div class="note"><b>诚实的边界：</b>对汉族专属、名字独一无二的非遗（福船 / 书法 / 古琴），保留拼音专名或加中国限定，能既出海又不被稀释；
 但跨境共享的少数民族非遗（呼麦 / 木卡姆 / 玛纳斯），本族音译名照样高噪声——遗产本身跨国，取名救不了，得靠内容里的中国语境标识。</div>
</div></section>

<section class="alt"><div class="wrap">
 <div class="sec-h">{seal("查实")}<div><p class="kicker">人工实证 · 把区间收成真值</p><h2 class="serif">机器划的线，对在哪、错在哪</h2></div></div>
 <p class="lead">最容易出错的，是那 {hc_reviewed} 条机器判“相关”、却被过滤剔除的头部视频——它们决定了触达到底落在哪。
 我们逐条人工裁决：<b>{hc_noise_pct}% 的播放确属撞词噪声</b>（过滤方向对了），
 但 <b>{hc_fk_pct}%（{short(fk.get("play",0))}）是被误杀的真内容</b>。</p>
 <div class="grid2">
  <div class="card big"><h3 style="color:#DA512F">过滤对了 · 撞词淹没型</h3><p>福船头部 25 条全部确认是噪声 → 真实触达就是 10 万；剪纸、书法的头部噪声也被人工坐实。这些项目的低触达不是误判，是真相。</p></div>
  <div class="card big"><h3 style="color:#48A89C">过滤过头了 · 本土化出海型</h3><p>太极被误杀 13 条 / 5650 万，全是“做给外国人看、不打 #china”的本土化内容；长调下界仅 36 万，人工确认 1.5 亿全真（跨境蒙古族、零中文标记，过滤砍掉 99.8%）。</p></div>
 </div>
 <div class="note">误杀的真内容分两种成因：<b>本土化无中国标记 {an.get("localized_no_marker_n",0)} 条 / {short(an.get("localized_no_marker_play",0))}</b>——做给外国人、不打任何中国标签，文本过滤<b>结构上救不了</b>，指向“隐形”假设的不可消除偏差；
 <b>漏检的中国语境 {an.get("china_context_n",0)} 条 / {short(an.get("china_context_play",0))}</b>——其实有中国语境、过滤没识别到，原则上可补。
 换句话说：机器测文化出海既会<b>系统高估</b>（撞词混入），又会<b>系统低估</b>（本土化出海被滤掉）——两个方向的误差都被这次人工核查量化了。</div>
</div></section>

<section><div class="wrap">
 <div class="sec-h">{seal("脆弱")}<div><p class="kicker">原创发现 · 重新定义“成功”</p><h2 class="serif">高触达，不等于真扩散</h2></div></div>
 <p class="lead">有些项目的“破圈”其实靠一个博主独力支撑——那人一停就归零。下图越红越脆弱：
 蚕桑 74%、粤剧 68%、龙泉青瓷 55% 的触达压在单一账号上；春节(6%)、针灸(13%)、呼麦(14%)才是去中心化的稳健扩散。</p>
 <div class="fig">{f_au}</div>
 <p class="cap">top1 作者播放占比，仅统计中国信号过滤后的触达池；“n视频/号”为样本量。</p>
</div></section>

<section class="alt"><div class="wrap">
 <div class="sec-h">{seal("两台")}<div><p class="kicker">假设四 · 背景</p><h2 class="serif">同一项非遗，两个平台两副面孔</h2></div></div>
 <p class="lead">15 个双平台都采到的项目里，没有一项相对更靠 YouTube——TikTok 是几乎所有非遗的更广触达盘。
 但太极、古琴、蚕桑这类“慢内容”在 YouTube 绝对值反超，找到了不成比例的位置。
 <span style="color:#9F9580">（跨平台只比各平台内部相对位置，不比绝对值——两平台过滤精度与采集深度不同。）</span></p>
 <div class="fig" style="padding:20px">{xp_table(xp)}</div>
</div></section>

<section><div class="wrap">
 <div class="sec-h">{seal("方法")}<div><p class="kicker">方法与边界</p><h2 class="serif">我们怎么数，以及数不到什么</h2></div></div>
 <div class="cards">
  <div class="card"><h3>搜索是工具，刷到是触达</h3><p>用关键词发现视频，但播放量主要来自 For You 推荐——衡量的是“被刷到”的程度，不是被搜的次数。</p></div>
  <div class="card"><h3>触达是区间，不是一个数</h3><p>下界=中国信号过滤，上界=机器宽口径。区间宽度本身就是“身份稀释度”证据，故不藏不平。</p></div>
  <div class="card"><h3>头部由人工定真值</h3><p>播放高度长尾，每项头部几十条≈全部触达。{hc_reviewed} 条撞词嫌疑头部已逐条人工核查，触达锚点为人工实证。</p></div>
  <div class="card"><h3>机器会双向出错</h3><p>既系统高估（撞词混入）、又系统低估（本土化出海被滤掉）——本身就是“算法测文化传播会错在哪”的发现。</p></div>
  <div class="card"><h3>看不到“无标记的出海”</h3><p>纯画面、无任何文本线索的中国非遗，文本方法判不了——这是方法的边界，不是结论。</p></div>
 </div>
</div></section>

<footer class="wrap">
 数据：TikTok 单区基准采集（2026-06）× YouTube Data API 深采对照。触达口径为中国信号过滤区间，
 头部 {hc_reviewed} 条撞词嫌疑视频已人工核查、触达锚点为人工实证，跨平台 15 项可比。
</footer>
</div>"""
    # Artifact 版:title+style+body+script 片段(发布时由 Artifact 包外层)
    artifact=f"<title>{title}</title>\n{CSS}\n{body}\n{js}"
    OUT.write_text(artifact, encoding="utf-8")
    # 独立可分发版:完整 HTML 文档
    standalone=("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                f"<title>{title}</title>\n{CSS}\n</head>\n<body>\n{body}\n{js}\n</body>\n</html>")
    STANDALONE.write_text(standalone, encoding="utf-8")
    print(f"wrote {OUT.name} ({len(artifact)}c) + standalone ({len(standalone)}c); "
          f"hero {short_cn(tot_m)}->{short_cn(tot_a)} shrink {shrink}% collapse{n_collapse} invis{n_invis}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
