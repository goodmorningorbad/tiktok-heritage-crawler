#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_dejunk_and_2d_consolidation_20260627.py

收口三件事(Cloud 2026-06-27 拍板),只读不可变基线/既有派生 + 写派生/交接包,不动原始捕获:

1) 福船(pid12)剔除 junk + watertight 两个【查询错误词】(纯西化泛词,~100%噪声,0%中国;
   官方名本是 "Chinese junks")。这是【纠错】非洗数据:它们不是福船的稀释证据,是测量假象。
   原始 row_labels/sched_run 一行不动,仅在派生层剔除。

2) 全部口径改成 2D:【绝对真实播放=标尺/能见度本体】 × 【份额=透镜/是否被淹】。
   绝对值用 378 头部人工核查锚定后的 reach_human_anchored(项目级核查已折入)。
   四象限: 独占且被看见 / 挤着但被看见 / 独占但小众 / 真隐形。

3) 名字/识别词级指标一律换成【播放份额】(废条数噪声),并结合 378 核查回补误杀真play。

输出:
  data/derived/tiktok_dejunk_2d_consolidated_20260627.json   (派生权威产物 + 福船纠错审计)
  docs/design_handoff_20260627/data/figures_data.json        (就地补 2D 字段 + 福船纠错 + collapse 重算)
  docs/design_handoff_20260627/data/recognition_rounds.json  (补绝对play + 份额双值, 结合核查)
"""
import json, csv, collections, io, sys

RL   = "data/final/tiktok_closed_20260619/row_labels/tiktok_video_relevance_labels_final.ndjson"
HCL  = "data/derived/tiktok_head_check_list_20260620.csv"
HCR  = "data/review/tiktok_head_check_returned_20260620.csv"
FD   = "docs/design_handoff_20260627/data/figures_data.json"
RR   = "docs/design_handoff_20260627/data/recognition_rounds.json"
OUT  = "data/derived/tiktok_dejunk_2d_consolidated_20260627.json"

FUCHUAN_PID = 12
BAD_TERMS = {"junk", "watertight"}     # 查询错误词,派生层剔除

# 四象限阈值(绝对play=被看见的门槛 / 份额=独占赛道的门槛),可调
ABS_SEEN = 30_000_000
SHARE_OWN = 50.0

def cn_num(n):
    n = float(n)
    if n >= 1e8: return f"{n/1e8:.2f}亿"
    if n >= 1e4: return f"{n/1e4:.1f}万"
    return f"{int(n)}"

# ---------- 载入 378 核查: 词级误杀(human=relevant)真play ----------
hcl = {}
with open(HCL, encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        hcl[r["check_id"]] = {"term": r["source_term"], "play": int(r["play_count"]), "pid": int(r["project_id"])}
fk_by_term = collections.Counter()
with open(HCR, encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        if r.get("manual_relevant") == "relevant":
            t = hcl.get(r["check_id"], {}).get("term")
            if t: fk_by_term[t] += hcl[r["check_id"]]["play"]

# ---------- 词级: china_context 绝对play + 总play (from row_labels) ----------
term_agg = collections.defaultdict(lambda: {"play": 0, "cn": 0})
# 福船纠错复算(dedup by video_id)
fc_all, fc_dejunk = {}, {}
for line in open(RL, encoding="utf-8"):
    if not line.strip(): continue
    r = json.loads(line)
    st = r.get("source_term") or ""
    p = r.get("stats_play_count") or 0
    a = term_agg[st]; a["play"] += p
    if r.get("china_context_hit"): a["cn"] += p
    if r.get("project_id") == FUCHUAN_PID:
        vid = r.get("video_id")
        likely = r.get("quality_label") == "likely_relevant"
        signal = bool(r.get("china_context_hit") or r.get("has_cjk_desc"))
        for d, ok in ((fc_all, True), (fc_dejunk, st not in BAD_TERMS)):
            if not ok: continue
            if vid not in d: d[vid] = [p, signal, likely]
            else:
                d[vid][1] = d[vid][1] or signal; d[vid][2] = d[vid][2] or likely

def reach(d):
    mach = sum(p for p, s, l in d.values() if l)
    floor = sum(p for p, s, l in d.values() if l and s)
    return mach, floor

fc_mach0, fc_floor0 = reach(fc_all)
fc_mach1, fc_floor1 = reach(fc_dejunk)

def term_row(t):
    a = term_agg[t]; fk = fk_by_term.get(t, 0)
    real = a["cn"] + fk
    return {"term": t, "total_play": a["play"], "cn_context_play": a["cn"],
            "head_check_addback": fk, "real_abs": real,
            "cn_play_share_pct": round(100 * real / max(a["play"], 1), 1)}

# ---------- 项目级: 载入既有 figures_data, 福船纠错, 加 2D 字段 ----------
fd = json.load(open(FD, encoding="utf-8"))

# 福船纠错: 25 条核查全是 junk/watertight(全判无关) -> 剔除后无核查行, anchored=floor
fc_audit = {"pid": FUCHUAN_PID, "before": {"machine": fc_mach0, "floor": fc_floor0},
            "after_dejunk": {"machine": fc_mach1, "floor": fc_floor1},
            "removed_terms": sorted(BAD_TERMS),
            "removed_machine_play": fc_mach0 - fc_mach1,
            "note": "福船25条头部核查全部是junk(19)+watertight(6)且全判irrelevant; 剔两词后福船无任何核查行, 人工锚定=信号过滤下界"}

old_machine_sum = sum(p["reach_machine"] for p in fd["projects"])
old_anchored_sum = sum(p["reach_anchored"] for p in fd["projects"])

for p in fd["projects"]:
    if p["id"] == FUCHUAN_PID:
        p["reach_machine"] = fc_mach1
        p["reach_floor"] = fc_floor1
        p["reach_anchored"] = fc_floor1
        p["reach_machine_cn"] = cn_num(fc_mach1)
        p["reach_anchored_cn"] = cn_num(fc_floor1)
        p["dilution_pct"] = round(100 * (fc_mach1 - fc_floor1) / max(fc_mach1, 1))
        p["head_false_kill_n"] = 0; p["head_false_kill_play"] = 0; p["fk_localized_n"] = 0
        p["dejunk_corrected"] = True
    # 2D 字段
    share = 100 * p["reach_anchored"] / max(p["reach_machine"], 1)
    p["share_real_pct"] = round(share)
    hi_abs = p["reach_anchored"] >= ABS_SEEN
    hi_sh = share >= SHARE_OWN
    p["fate"] = ("独占且被看见" if hi_abs and hi_sh else
                 "独占但小众" if hi_sh else
                 "挤着但被看见" if hi_abs else "真隐形")

# ---------- collapse_aggregate 重算 ----------
new_machine = sum(p["reach_machine"] for p in fd["projects"])
new_anchored = sum(p["reach_anchored"] for p in fd["projects"])
n_collapse = sum(1 for p in fd["projects"]
                 if p["reach_machine"] > 0 and (p["reach_machine"] - p["reach_anchored"]) / p["reach_machine"] >= 0.60)
n_invis = sum(1 for p in fd["projects"] if p["reach_anchored"] < 1_000_000)
fate_counts = collections.Counter(p["fate"] for p in fd["projects"])
fd["collapse_aggregate"] = {
    "machine": new_machine, "anchored": new_anchored,
    "machine_cn": cn_num(new_machine), "anchored_cn": cn_num(new_anchored),
    "shrink_pct": round(100 * (1 - new_anchored / new_machine)),
    "n_collapse_ge60": n_collapse, "n_invisible_under_1m": n_invis,
    "_note": f"福船剔junk+watertight后机器聚合 {cn_num(old_machine_sum)}→{cn_num(new_machine)}; 真值聚合基本不变(福船真值本就~5万)。锚定=378核查; 标尺=绝对真实播放, 份额仅作透镜。"
}
fd["fate_counts"] = dict(fate_counts)
fd["fate_thresholds"] = {"abs_seen": ABS_SEEN, "share_own_pct": SHARE_OWN,
                         "_axes": "abs=reach_anchored(378核查锚定,绝对能见度); share=anchored/machine(是否被淹). 阈值可调,原始值都在projects里"}

# ---------- 名字块: 换成播放份额 + 龙泉青瓷为典型 + 福船认账 ----------
naming_terms = {
    "龙泉青瓷传统烧制技艺": [("celadon","纯西化译词"),("longquanceladon","地名复合"),("龙泉","地名锚·CJK"),("青瓷","CJK通用")],
    "中国书法": [("calligraphy","纯西化译词"),("shufa","拼音专名"),("chineseink","Chinese+限定")],
    "中国剪纸": [("papercut","纯西化译词"),("papercutting","纯西化译词"),("chinesepapercut","Chinese+限定")],
    "中国珠算": [("abacus","纯西化译词"),("zhusuan","拼音专名")],
    "中国篆刻": [("sealcarving","纯西化译词"),("chineseseal","Chinese+限定")],
    "中国水密隔舱福船制造技艺": [("fuchuan","拼音专名")],  # junk/watertight 已认账剔除
}
naming = []
for proj, varlist in naming_terms.items():
    vs = []
    for t, typ in varlist:
        rw = term_row(t); rw["type"] = typ
        vs.append(rw)
    naming.append({"project": proj, "variants": vs})
fd["naming"] = naming
fd["_naming_about"] = ("名字轴=【按播放份额(能见度)】,非条数噪声。结论(2026-06-27勘误): 罗马音救不了(shufa3%/fuchuan3%/zhusuan22%),"
                       "通用译词被淹但内容能打的仍有大绝对量(calligraphy12%但8500万真play); 真正拉起能见度的是【地域/民族/节庆锚点】的复合名"
                       "(龙泉青瓷: celadon52%→龙泉73%)。锚点不是营销可调,是非遗自带的结构属性。junk/watertight 是我们查询用错的词,已剔并认账。")

# 兼容旧 _about 防混淆注(改成份额口径)
fd["_about"] = ("页面展示用的全部数字(compact)。源自 data/derived/* + row_labels + 378头部人工核查,已就绪。"
                "口径(2026-06-27终态): 标尺=reach_anchored(绝对真实播放/能见度); 份额=share_real_pct(透镜,是否被淹),不参与隐形排名。"
                "四象限见 fate/fate_counts。名字/识别一律用播放份额,不用条数撞词率。不预设任何通用词(papercut/celadon)本该属于中国,低份额≠身份失败。")

json.dump(fd, open(FD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- recognition_rounds: 补绝对play + 核查, 改 headline ----------
rr = json.load(open(RR, encoding="utf-8"))
rtab = {"papercut": term_row("papercut"), "calligraphy": term_row("calligraphy"), "abacus": term_row("abacus")}
heads = {
 "papercut": "中国剪纸在 papercut 赛道既不独占也没被看见: 真实绝对播放仅 1,414, 份额 0% —— 真·隐形。",
 "calligraphy": "对照组: 份额只有 11.7%(挤在巨大的书法赛道里), 但真实绝对播放 ≈8500万 —— 看份额像被淹, 看绝对量其实被大量看见。",
 "abacus": "珠算: 结合378核查后真实绝对播放 ≈9900万、份额 25.9%(机器漏检的中国珠算被人工补回); 赛道仍被日式そろばん/珠心算机构占据。",
}
for rd in rr["rounds"]:
    t = rd["term"]; tr = rtab.get(t)
    if tr:
        rd["cn_play_abs"] = tr["real_abs"]
        rd["cn_play_share_pct"] = tr["cn_play_share_pct"]
        rd["total_play"] = tr["total_play"]
        rd["head_check_addback"] = tr["head_check_addback"]
        rd["headline"] = heads[t]
rr["_metrics"] = ("cn_play_abs=真实中国绝对播放【标尺/能见度本体】=china_context + 378核查误杀回补; cn_play_share_pct=该赛道里中国占的播放份额【透镜/是否被淹】。"
                  "口径(Cloud 2026-06-27): 先看绝对(书法8500万=被大量看见), 份额只解释'在不在大赛道里挤'。绝不用份额给隐形排名。"
                  "rate(条数撞词率)只用来说'你刷到的大多不是它'。real=该卡是否真·中国非遗。abs为下界(china_context代理+头部核查,漏无标记本土化)。")
json.dump(rr, open(RR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 派生权威产物 ----------
out = {
    "date": "20260627",
    "fuchuan_dejunk_audit": fc_audit,
    "collapse_aggregate": fd["collapse_aggregate"],
    "fate_counts": dict(fate_counts),
    "projects_2d": [{"id": p["id"], "name_cn": p["name_cn"],
                     "reach_anchored": p["reach_anchored"], "reach_machine": p["reach_machine"],
                     "share_real_pct": p["share_real_pct"], "fate": p["fate"]} for p in fd["projects"]],
    "recognition_terms": rtab,
    "naming_play_share": naming,
}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 控制台报告 ----------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
print("=== 福船纠错 ===")
print(f"  机器 {cn_num(fc_mach0)} → {cn_num(fc_mach1)}  (剔除 junk+watertight {cn_num(fc_mach0-fc_mach1)} 纯噪声)")
print(f"  真值(锚定) {cn_num(fc_floor0)} → {cn_num(fc_floor1)}")
print("=== collapse 聚合重算 ===")
print(f"  机器 {cn_num(old_machine_sum)} → {cn_num(new_machine)} ; 真值 {cn_num(old_anchored_sum)} → {cn_num(new_anchored)} ; 缩水 {fd['collapse_aggregate']['shrink_pct']}%")
print(f"  塌缩≥60%项目 {n_collapse} ; 隐形<100万 {n_invis}")
print("=== 四象限 ===", dict(fate_counts))
print("=== 已写 ===", OUT, "+", FD, "+", RR)
