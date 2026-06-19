# -*- coding: utf-8 -*-
"""
Score AI relevance audit output against a human answer key.

Usage:
  python3 scripts/score_ai_audit.py ai_results.jsonl \
    --answer-key data/derived/ai_audit_validation_answer_key_358_20260619.json

AI results: one JSON object per line with at least {"id": ..., "verdict": ...}.
Accepted verdict aliases are normalized to: 相关 / 不相关 / 拿不准.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ALIASES = {
    "相关": "相关",
    "relevant": "相关",
    "likely_relevant": "相关",
    "yes": "相关",
    "不相关": "不相关",
    "irrelevant": "不相关",
    "low_relevance": "不相关",
    "no": "不相关",
    "拿不准": "拿不准",
    "uncertain": "拿不准",
    "needs_review": "拿不准",
    "不确定": "拿不准",
}
LABELS = ["相关", "不相关", "拿不准"]


def norm_label(value: object) -> str:
    s = str(value or "").strip()
    return ALIASES.get(s, ALIASES.get(s.lower(), s))


def load_jsonl(path: Path) -> tuple[dict[str, str], int]:
    out: dict[str, str] = {}
    bad = 0
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                vid = str(d["id"]).strip()
                out[vid] = norm_label(d.get("verdict", d.get("label", "")))
            except Exception as exc:  # report malformed model rows
                bad += 1
                print(f"解析失败 line {lineno}: {exc}: {line[:120]}", file=sys.stderr)
    return out, bad


def safe_pct(num: int, den: int) -> float:
    return (num / den * 100.0) if den else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ai_results", nargs="?", default="ai_results.jsonl")
    ap.add_argument("--answer-key", default="data/derived/ai_audit_validation_answer_key_358_20260619.json")
    args = ap.parse_args()

    answer_key = {str(k): norm_label(v) for k, v in json.load(open(args.answer_key, encoding="utf-8")).items()}
    ai, bad = load_jsonl(Path(args.ai_results))

    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    missing = 0
    total = 0
    matched = 0
    unexpected = Counter()
    for vid, human_v in answer_key.items():
        if vid not in ai:
            missing += 1
            continue
        total += 1
        ai_v = ai[vid]
        if ai_v not in LABELS:
            unexpected[ai_v] += 1
        confusion[human_v][ai_v] += 1
        if ai_v == human_v:
            matched += 1

    print("=== 总体 ===")
    print(f"AI覆盖: {total}/{len(answer_key)} (缺{missing}, JSON坏行{bad})")
    if total == 0:
        print("没有可评分记录。")
        return 2
    print(f"总一致率: {matched}/{total} = {safe_pct(matched, total):.1f}%")
    print("注意: 总一致率仍会受类别分布影响，重点看分类召回/精确率和误报。")

    print("\n=== 分类混淆矩阵(人工 → AI) ===")
    for human_v in LABELS:
        row = confusion[human_v]
        rtot = sum(row.values())
        if not rtot:
            continue
        print(f"\n人工判[{human_v}] 共{rtot}条, AI判成:")
        for ai_v, c in row.most_common():
            flag = " ✓" if ai_v == human_v else " ✗"
            print(f"    {ai_v}: {c} ({safe_pct(c, rtot):.0f}%){flag}")

    print("\n=== 关键指标 ===")
    human_rel_total = sum(confusion["相关"].values())
    rel_recall = confusion["相关"].get("相关", 0) / max(human_rel_total, 1)
    ai_rel_total = sum(confusion[h].get("相关", 0) for h in LABELS)
    rel_precision = confusion["相关"].get("相关", 0) / max(ai_rel_total, 1)
    ai_irrel_total = sum(confusion[h].get("不相关", 0) for h in LABELS)
    irrel_precision = confusion["不相关"].get("不相关", 0) / max(ai_irrel_total, 1)
    false_positive = sum(confusion[h].get("相关", 0) for h in ["不相关", "拿不准"])
    false_positive_rate = false_positive / max(ai_rel_total, 1)
    uncertain_rate = sum(confusion[h].get("拿不准", 0) for h in LABELS) / max(total, 1)
    accuracy = matched / total
    print(f"相关召回率: {rel_recall*100:.1f}%")
    print(f"相关精确率: {rel_precision*100:.1f}%")
    print(f"不相关精确率: {irrel_precision*100:.1f}%")
    print(f"AI判相关中的误报率: {false_positive_rate*100:.1f}%")
    print(f"AI拿不准比例: {uncertain_rate*100:.1f}%")
    if unexpected:
        print(f"未识别标签: {dict(unexpected)}")

    print("\n=== 判定 ===")
    if accuracy >= 0.85 and rel_precision >= 0.85 and irrel_precision >= 0.85 and rel_recall >= 0.70:
        print("✅ 通过：可进入 YouTube 批量 AI 核查。")
        return 0
    print("⚠️ 未完全通过：先看混淆样本，调 prompt 或保守融合后再批量用。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
