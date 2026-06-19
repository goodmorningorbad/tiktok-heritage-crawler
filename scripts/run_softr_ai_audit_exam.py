#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the 358-row AI audit validation exam through the local SoftrPool proxy.

Writes one normalized JSON object per input row and supports resume by id.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LABELS = {"相关", "不相关", "拿不准"}
NOISE_TYPES = {"别国同类", "主题无关", "泛科普或产品", "衍生品", "无"}
LABEL_ALIASES = {
    "relevant": "相关",
    "irrelevant": "不相关",
    "uncertain": "拿不准",
    "likely_relevant": "相关",
    "low_relevance": "不相关",
    "needs_review": "拿不准",
    "yes": "相关",
    "no": "不相关",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_done(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("verdict") in LABELS:
                    done.add(str(d.get("id")))
            except Exception:
                continue
    return done


def extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError(f"no JSON object in output: {text[:200]!r}")
    return json.loads(m.group(0))


def normalize(row: dict[str, Any], raw_text: str, response: dict[str, Any], elapsed: float) -> dict[str, Any]:
    d = extract_json(raw_text)
    verdict = str(d.get("verdict", d.get("label", ""))).strip()
    verdict = LABEL_ALIASES.get(verdict, LABEL_ALIASES.get(verdict.lower(), verdict))
    if verdict not in LABELS:
        raise ValueError(f"bad verdict {verdict!r} from {raw_text[:200]!r}")
    noise_type = str(d.get("noise_type", "无")).strip() or "无"
    if noise_type not in NOISE_TYPES:
        # Keep scoring robust while preserving the model's raw value.
        noise_type = "无" if verdict == "相关" else "主题无关"
    if verdict == "相关":
        noise_type = "无"
    reason = str(d.get("reason", "")).strip().replace("\n", " ")[:60]
    return {
        "id": str(row["id"]),
        "project": row.get("project", ""),
        "verdict": verdict,
        "noise_type": noise_type,
        "reason": reason,
        "raw_output": raw_text,
        "softr": response.get("softr", {}),
        "elapsed_s": round(elapsed, 3),
    }


def call_proxy(endpoint: str, model: str, system_prompt: str, row: dict[str, Any], timeout: int) -> tuple[str, dict[str, Any], float]:
    user_obj = {
        "id": str(row.get("id", "")),
        "project": row.get("project", ""),
        "desc": row.get("desc", ""),
        "hashtags": row.get("hashtags", ""),
        "author": row.get("author", ""),
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_obj, ensure_ascii=False)},
        ],
        "temperature": 0,
        "max_tokens": 1049,
        "stream": False,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0
    text = payload["choices"][0]["message"].get("content", "")
    return text, payload, elapsed


def run_one(row: dict[str, Any], args: argparse.Namespace, system_prompt: str) -> dict[str, Any]:
    last_err = None
    for attempt in range(1, args.retries + 1):
        try:
            raw_text, payload, elapsed = call_proxy(args.endpoint, args.model, system_prompt, row, args.timeout)
            return normalize(row, raw_text, payload, elapsed)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
            last_err = repr(exc)
            time.sleep(min(2 * attempt, 10))
    return {
        "id": str(row["id"]),
        "project": row.get("project", ""),
        "verdict": "拿不准",
        "noise_type": "主题无关",
        "reason": "调用失败",
        "error": last_err,
        "elapsed_s": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/derived/ai_audit_validation_exam_358_20260619.jsonl")
    ap.add_argument("--prompt", default="_incoming_ai_audit_files/judging_prompt_v2.md")
    ap.add_argument("--output", default="data/derived/ai_audit_exam_results_softr_20260619.jsonl")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8321/v1/chat/completions")
    ap.add_argument("--model", default="anthropic-claude-opus-4-8")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=150)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard-index", type=int, default=0, help="0-based shard index")
    ap.add_argument("--shard-count", type=int, default=1, help="total number of shards")
    args = ap.parse_args()

    rows = load_jsonl(Path(args.input))
    if args.shard_count < 1 or args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise SystemExit("invalid shard args")
    if args.shard_count > 1:
        rows = [r for i, r in enumerate(rows) if i % args.shard_count == args.shard_index]
    if args.limit:
        rows = rows[: args.limit]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = load_done(out)
    todo = [r for r in rows if str(r["id"]) not in done]
    system_prompt = Path(args.prompt).read_text(encoding="utf-8")
    lock = threading.Lock()
    start = time.time()
    print(f"rows={len(rows)} done={len(done)} todo={len(todo)} workers={args.workers} output={out}", flush=True)
    if not todo:
        return 0

    completed = 0
    with out.open("a", encoding="utf-8") as f, cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, row, args, system_prompt): row for row in todo}
        for fut in cf.as_completed(futs):
            res = fut.result()
            with lock:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
                f.flush()
                completed += 1
                if completed % 10 == 0 or completed == len(todo):
                    rate = completed / max(time.time() - start, 1)
                    print(f"progress {completed}/{len(todo)} rate={rate:.2f}/s last={res['id']} verdict={res['verdict']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
