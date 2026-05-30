#!/usr/bin/env python3
"""First-pass quality audit and relevance labeling for UNESCO TikTok dataset.

Input: CSV exported by batch_collect.py
Output:
- row-level labeled CSV
- project-level summary CSV
- JSON report

This is deliberately conservative: it does not delete rows; it adds labels so
manual review / later model-based cleaning can decide thresholds.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

GENERIC_WEAK_TERMS = {
    "china", "chinese", "culture", "traditional", "tradition", "art", "music",
    "dance", "opera", "festival", "springfestival", "chineseopera", "martialarts",
    "folksong", "kyrgyz", "mongolian", "xinjiang", "fujian", "yangzhou",
}

CHINA_CONTEXT_TERMS = {
    "china", "chinese", "中国", "中华", "中文", "华人", "华裔", "cny", "lunarnewyear",
    "chinesenewyear", "springfestival", "mandarin", "tiktokchina", "抖音",
}

PROJECT_EXTRA_TERMS: dict[str, set[str]] = {
    "春节": {"春节", "新年", "过年", "chinesenewyear", "lunarnewyear", "cny", "springfestival", "gongxifacai", "新年快乐"},
    "中国传统制茶技艺及其相关习俗": {"茶", "茶艺", "中国茶", "gongfutea", "gongfucha", "chinesetea", "teaceremony", "teaculture", "puer", "puerh"},
    "太极拳": {"太极", "太极拳", "taichi", "taijiquan"},
    "送王船": {"送王船", "王船", "ongchun", "wangchuan", "wangkang", "boatburning"},
    "藏医药浴法": {"藏医", "药浴", "sowarigpa", "tibetanmedicine", "tibetanhealing"},
    "二十四节气": {"二十四节气", "节气", "solarterms", "24solarterms", "chinesecalendar"},
    "中国珠算": {"珠算", "算盘", "abacus", "zhusuan"},
    "福建木偶戏": {"木偶", "布袋戏", "puppet", "puppetry", "budaixi", "fujianpuppet"},
    "赫哲族伊玛堪": {"赫哲", "伊玛堪", "hezhe", "yimakan"},
    "中国皮影戏": {"皮影", "皮影戏", "shadowpuppet", "shadowpuppetry", "piying"},
    "麦西热甫": {"麦西热甫", "meshrep", "mäshräp", "uyghur"},
    "中国水密隔舱福船制造技艺": {"水密隔舱", "福船", "watertight", "junk", "fuchuan"},
    "中国木活字印刷术": {"木活字", "活字", "movabletype", "woodentype", "printing"},
    "京剧": {"京剧", "pekingopera", "beijingopera", "chineseopera"},
    "中医针灸": {"针灸", "acupuncture", "tcm", "chinesemedicine"},
    "黎族传统纺染织绣技艺": {"黎族", "织锦", "纺染", "liethnic", "brocade", "textile"},
    "中国木拱桥传统营造技艺": {"木拱桥", "廊桥", "woodenarchbridge", "coveredbridge"},
    "羌年": {"羌年", "羌族", "qiangnewyear", "qiang"},
    "侗族大歌": {"侗族", "侗族大歌", "kamgrandchoir", "dongchorus"},
    "西安鼓乐": {"西安鼓乐", "鼓乐", "xianwind", "drummusic"},
    "中国蚕桑丝织技艺": {"蚕桑", "丝织", "silk", "sericulture", "silkweaving"},
    "南音": {"南音", "nanyin", "nanguan", "quanzhoumusic"},
    "南京云锦织造技艺": {"云锦", "南京云锦", "yunjin", "nanjingbrocade"},
    "宣纸传统制作技艺": {"宣纸", "xuanpaper", "ricepaper", "papermaking"},
    "粤剧": {"粤剧", "cantoneseopera", "yueopera"},
    "格萨(斯)尔史诗传统": {"格萨尔", "格萨", "gesar", "epic"},
    "龙泉青瓷传统烧制技艺": {"龙泉", "青瓷", "longquanceladon", "celadon"},
    "热贡艺术": {"热贡", "唐卡", "regong", "thangka"},
    "藏戏": {"藏戏", "tibetanopera", "lhamo", "achelhamo"},
    "玛纳斯": {"玛纳斯", "manas", "kyrgyz"},
    "蒙古族呼麦": {"呼麦", "khoomei", "throatsinging", "mongolian"},
    "花儿": {"花儿", "huaer", "northwestchinasong"},
    "中国朝鲜族农乐舞": {"农乐舞", "朝鲜族", "nongak", "farmersdance"},
    "中国书法": {"书法", "calligraphy", "shufa", "chineseink"},
    "中国篆刻": {"篆刻", "印章", "sealcarving", "chineseseal"},
    "中国剪纸": {"剪纸", "papercut", "papercutting", "chinesepapercut"},
    "中国传统木结构建筑营造技艺": {"斗拱", "古建", "木结构", "timberframe", "chinesearchitecture"},
    "端午节": {"端午", "端午节", "dragonboat", "duanwu", "zongzi"},
    "妈祖信俗": {"妈祖", "mazu", "seagoddess"},
    "中国雕版印刷技艺": {"雕版", "雕版印刷", "blockprinting", "woodblock"},
    "昆曲": {"昆曲", "kunqu", "kunopera", "kunquopera"},
    "古琴艺术": {"古琴", "guqin", "chinesezither"},
    "新疆维吾尔木卡姆艺术": {"木卡姆", "muqam", "uyghurmuqam"},
    "蒙古族长调民歌": {"长调", "longsong", "urtiinduu", "mongoliansong"},
}


def norm_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    # keep CJK and alnum, remove separators for robust hashtag matching
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", s)


def split_terms(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,/;|\s]+", value)
    return [p.strip().lstrip("#").lower() for p in parts if p.strip().lstrip("#")]


def parse_int(v) -> int:
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def label_row(row: dict) -> dict:
    project = row.get("heritage_name_cn", "")
    source = (row.get("source") or "").strip().lstrip("#").lower()
    desc = row.get("desc") or ""
    hashtags = row.get("hashtags") or ""
    hashtags_text = row.get("hashtags_text") or ""
    text_raw = " ".join([desc, hashtags, hashtags_text, row.get("author_nickname") or "", row.get("music_title") or ""])
    text = norm_text(text_raw)

    terms = set(PROJECT_EXTRA_TERMS.get(project, set()))
    # add source itself, but mark whether it is weak/generic
    if source:
        terms.add(source)
    terms_norm = {norm_text(t) for t in terms if norm_text(t)}

    hit_set = {t for t in terms_norm if t and t in text}
    hits = sorted(hit_set)
    source_hit = bool(source and norm_text(source) in text)
    china_context = any(norm_text(t) in text for t in CHINA_CONTEXT_TERMS)
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", desc))
    weak_source = source in GENERIC_WEAK_TERMS

    score = 0
    reasons = []
    if source_hit:
        score += 2
        reasons.append("source_hit")
    if hits:
        score += min(4, len(hits))
        reasons.append(f"project_term_hits:{len(hits)}")
    if china_context:
        score += 1
        reasons.append("china_context")
    if has_cjk:
        score += 1
        reasons.append("cjk_desc")
    if parse_int(row.get("stats_play_count")) == 0:
        score -= 1
        reasons.append("zero_play")
    if not desc.strip():
        score -= 2
        reasons.append("empty_desc")
    if weak_source and not (hit_set - {norm_text(source)}):
        score -= 2
        reasons.append("generic_source_only")

    if score >= 4:
        label = "likely_relevant"
    elif score >= 2:
        label = "needs_review"
    else:
        label = "low_relevance"

    row = dict(row)
    row.update({
        "quality_score": score,
        "quality_label": label,
        "quality_reasons": ";".join(reasons),
        "matched_terms": ",".join(hits[:20]),
        "source_hit_in_text": str(source_hit).lower(),
        "china_context_hit": str(china_context).lower(),
        "has_cjk_desc": str(has_cjk).lower(),
        "weak_generic_source": str(weak_source).lower(),
    })
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv")
    ap.add_argument("--out-prefix", default=None)
    args = ap.parse_args()

    inp = Path(args.input_csv)
    prefix = Path(args.out_prefix) if args.out_prefix else inp.with_suffix("")
    labeled_path = Path(str(prefix) + "_labeled.csv")
    summary_path = Path(str(prefix) + "_project_quality_summary.csv")
    report_path = Path(str(prefix) + "_quality_report.json")

    with inp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [label_row(r) for r in reader]
        base_fields = reader.fieldnames or []

    extra_fields = [
        "quality_score", "quality_label", "quality_reasons", "matched_terms",
        "source_hit_in_text", "china_context_hit", "has_cjk_desc", "weak_generic_source",
    ]
    fields = base_fields + [f for f in extra_fields if f not in base_fields]
    with labeled_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    by_project: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_project[r.get("heritage_name_cn", "")].append(r)

    summary_fields = [
        "heritage_name_cn", "rows", "likely_relevant", "needs_review", "low_relevance",
        "likely_pct", "low_pct", "median_score", "source_hit_pct", "china_context_pct",
        "empty_desc", "empty_hashtags",
    ]
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_fields)
        w.writeheader()
        for project, items in sorted(by_project.items(), key=lambda kv: kv[0]):
            c = Counter(r["quality_label"] for r in items)
            scores = [int(r["quality_score"]) for r in items]
            n = len(items)
            w.writerow({
                "heritage_name_cn": project,
                "rows": n,
                "likely_relevant": c["likely_relevant"],
                "needs_review": c["needs_review"],
                "low_relevance": c["low_relevance"],
                "likely_pct": round(c["likely_relevant"] / n, 4) if n else 0,
                "low_pct": round(c["low_relevance"] / n, 4) if n else 0,
                "median_score": median(scores) if scores else 0,
                "source_hit_pct": round(sum(r["source_hit_in_text"] == "true" for r in items) / n, 4) if n else 0,
                "china_context_pct": round(sum(r["china_context_hit"] == "true" for r in items) / n, 4) if n else 0,
                "empty_desc": sum(not (r.get("desc") or "").strip() for r in items),
                "empty_hashtags": sum((r.get("hashtags") or "") in ("", "[]") for r in items),
            })

    label_counts = Counter(r["quality_label"] for r in rows)
    report = {
        "input_csv": str(inp),
        "rows": len(rows),
        "labeled_csv": str(labeled_path),
        "project_summary_csv": str(summary_path),
        "label_counts": dict(label_counts),
        "label_pct": {k: round(v / len(rows), 4) for k, v in label_counts.items()},
        "projects": len(by_project),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
