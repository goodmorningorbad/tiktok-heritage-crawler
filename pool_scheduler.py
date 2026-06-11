#!/usr/bin/env python3
"""TikTok search 账号轮换 + 冷却队列调度器（方案A）。

为什么不是 pool_runner？
  pool_runner 是"按项目静态分配给 slot、slot 串行跑完"的模型。一旦某号被限流，
  它分到的整批项目全废。本调度器改为：
    - 工作单元 = (项目, term) 最细粒度，限流时只损失一个 term，且该 term 重新入队
    - 账号 = 有限的 search 配额水龙头，被限会自动恢复（实测：限流绑 account 不绑 IP）
    - 预防性轮换：一个号连续成功若干 term 就主动让它进冷却，不等被限
    - 被限号进冷却队列，到期自动回池

底线（不可妥协）：
  failed(限流技术噪声) / zero_real(真实0结果) / has_data 严格分字段，绝不混。
  failed 的 term 重新入队重采；重采到上限仍 failed → 最终标 unresolved_failed，
  绝不当作 zero_real 进"低传播"结论。

输出：
  data/sched_run_<run_id>/
    videos.ndjson          # 所有采到的视频行（自带逐行溯源 collector_meta）
    term_results.ndjson    # 每个 (项目,term) 的最终 meta：result_class / depth_verdict / 重试次数
    scheduler_state.json   # 实时进度 + 账号状态，可中断恢复
    scheduler.log          # 运行日志
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "unesco_ich_keywords.v1.json"
DEFAULT_POOL = ROOT / "config" / "us_pool.json"
DATA_DIR = ROOT / "data"
DEFAULT_PYTHON = "/root/workspace/tiktok-api-venv/bin/python3"

# ---- 可调参数（保守默认，干净优先）----
TERMS_PER_ACCOUNT_BURST = 6      # 一个号连续成功多少 term 后主动进冷却（预防性，低于实测限流阈值）
PREVENTIVE_COOLDOWN = 90         # 预防性冷却秒数（成功后主动休息）
RATELIMIT_COOLDOWN = 1800        # 被限流后的惩罚冷却秒数（30min，实测短冷却救不回）
INTER_TERM_DELAY = 20            # 同号连续 term 之间的间隔秒数
MAX_TERM_RETRIES = 3             # 单个 term 因限流最多重采次数；超了标 unresolved_failed
PER_TERM_TIMEOUT = 600           # 单 term 子进程超时秒（头部项翻页可能久）


def log(state_dir: Path, msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (state_dir / "scheduler.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def build_accounts(pool: dict) -> list[dict]:
    """账号 ×（轮转复用）IP。限流绑 account 不绑 IP，所以账号数可多于 IP 数，复用 IP。"""
    accounts = pool["accounts"]
    proxies = pool["proxies"]
    out = []
    for i, a in enumerate(accounts):
        x = proxies[i % len(proxies)]   # 账号多于 IP 时轮转复用
        out.append({
            "account_id": a["id"],
            "account_role": a.get("role", "neutral"),
            "cookies": a["cookies"],
            "proxy_id": x["proxy_id"],
            "socks": x["socks"],
            "exit_ip": x.get("exit_ip", ""),
            "isp": x.get("isp", ""),
            "proxy_region": x.get("region", "unknown"),
            "proxy_subregion": x.get("subregion", ""),
            "proxy_pool": x.get("pool", ""),
            # 运行时状态
            "available_at": 0.0,     # 何时可用（冷却到期时间戳）
            "burst_count": 0,        # 当前连续成功计数
        })
    return out


def term_env(acc: dict, region_policy: str, phase: str) -> dict:
    env = os.environ.copy()
    env["TIKTOK_COOKIES_JSON"] = acc["cookies"]
    env["HTTPS_PROXY"] = acc["socks"]
    env["HTTP_PROXY"] = acc["socks"]
    env["TIKTOK_ACCOUNT_ID"] = acc["account_id"]
    env["TIKTOK_ACCOUNT_ROLE"] = acc["account_role"]
    env["TIKTOK_PROXY_REGION"] = acc["proxy_region"]
    env["TIKTOK_PROXY_SUBREGION"] = acc["proxy_subregion"]
    env["TIKTOK_PROXY_POOL"] = acc["proxy_pool"]
    env["TIKTOK_PROXY_ID"] = acc["proxy_id"]
    env["TIKTOK_PROXY_EXIT_IP"] = acc["exit_ip"]
    env["TIKTOK_PROXY_ISP"] = acc["isp"]
    env["TIKTOK_REGION_POLICY"] = region_policy
    env["COLLECTION_PHASE"] = phase
    env["TIKTOK_HEADLESS"] = "false"
    env.setdefault("TIKTOK_TIMEOUT_MS", "90000")
    # 调度器自己控制 term 间节奏，关掉 crawler 内置 term 延迟（单 term 调用用不到）
    env["TIKTOK_TERM_DELAY"] = "0"
    return env


def run_one_term(acc: dict, keyword: str, count: int, out_videos: Path,
                 region_policy: str, phase: str) -> dict:
    """跑单个 term。返回 meta dict（含 result_class）。子进程 crawler 把视频 append 到 out_videos。"""
    env = term_env(acc, region_policy, phase)
    cmd = ["xvfb-run", "-a", DEFAULT_PYTHON, "crawler.py", "search",
           "--keywords", keyword, "--count", str(count), "--out", str(out_videos)]
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True,
                           text=True, timeout=PER_TERM_TIMEOUT)
        allout = (r.stdout or "") + "\n" + (r.stderr or "")
        meta = None
        for line in allout.splitlines():
            if line.startswith("SEARCH_META "):
                try:
                    meta = json.loads(line.split(" ", 1)[1])
                except json.JSONDecodeError:
                    pass
        if meta is None:
            # 没解析到 meta：当作技术失败（不是 zero_real！），可重采
            meta = {"keyword": keyword, "collected_count": 0,
                    "depth_verdict": "no_meta", "result_class": "failed",
                    "error": f"no SEARCH_META; rc={r.returncode}; tail={allout[-300:]}"}
        return meta
    except subprocess.TimeoutExpired:
        return {"keyword": keyword, "collected_count": 0,
                "depth_verdict": "timeout", "result_class": "failed",
                "error": f"timeout>{PER_TERM_TIMEOUT}s"}


def pick_account(accounts: list[dict], now: float) -> dict | None:
    """挑一个当前可用（不在冷却）的号。优先 burst_count 低的（更凉）。"""
    avail = [a for a in accounts if a["available_at"] <= now]
    if not avail:
        return None
    avail.sort(key=lambda a: a["burst_count"])
    return avail[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="TikTok search 账号轮换+冷却队列调度器")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--pool", default=str(DEFAULT_POOL))
    ap.add_argument("--count", type=int, default=2000, help="每 term 上限（自适应触顶）")
    ap.add_argument("--limit-projects", type=int, default=0, help="只跑前N项，smoke用")
    ap.add_argument("--phase", default="search_baseline")
    ap.add_argument("--region-policy", default="single-region-baseline")
    ap.add_argument("--run-id", default=None, help="指定 run_id 以续跑（断点恢复）")
    args = ap.parse_args()

    base_cfg = load_json(Path(args.config))
    pool = load_json(Path(args.pool))
    projects = list(base_cfg.get("projects", []))
    if args.limit_projects:
        projects = projects[: args.limit_projects]

    accounts = build_accounts(pool)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    state_dir = DATA_DIR / f"sched_run_{run_id}"
    state_dir.mkdir(parents=True, exist_ok=True)
    out_videos = state_dir / "videos.ndjson"
    out_terms = state_dir / "term_results.ndjson"
    state_file = state_dir / "scheduler_state.json"

    # 断点恢复：已完成（has_data/zero_real/unresolved_failed）的 term 不重跑
    done_keys: set[str] = set()
    if out_terms.exists():
        for line in out_terms.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("result_class") in ("has_data", "zero_real", "unresolved_failed"):
                    done_keys.add(f"{rec['project_id']}::{rec['keyword']}")
            except Exception:
                pass

    # 构建工作队列：(项目, term) 最细粒度。同义大小写/单复数合并（只合并完全同义）
    queue: deque = deque()
    total_units = 0
    for proj in projects:
        terms = proj.get("search_terms") or []
        seen_norm = {}
        for t in terms:
            norm = t.strip().lower()
            if norm in seen_norm:        # 纯大小写/重复同义，合并
                continue
            seen_norm[norm] = t
        for t in seen_norm.values():
            key = f"{proj['id']}::{t}"
            if key in done_keys:
                continue
            queue.append({"project_id": proj["id"], "project_name": proj["name_cn"],
                          "keyword": t, "retries": 0})
            total_units += 1

    log(state_dir, f"=== 调度器启动 run_id={run_id} ===")
    log(state_dir, f"账号池={len(accounts)} 个 | 工作单元={total_units} 个 (项目×term) | 已完成跳过={len(done_keys)}")
    log(state_dir, f"参数: count={args.count} burst={TERMS_PER_ACCOUNT_BURST} "
                   f"预防冷却={PREVENTIVE_COOLDOWN}s 限流冷却={RATELIMIT_COOLDOWN}s")
    for a in accounts:
        log(state_dir, f"  号 {a['account_id']} @ {a['proxy_id']}({a['exit_ip']} {a['proxy_subregion']})")

    done = 0
    counts = {"has_data": 0, "zero_real": 0, "unresolved_failed": 0, "retry": 0}
    terms_f = out_terms.open("a", encoding="utf-8")

    while queue:
        now = time.time()
        acc = pick_account(accounts, now)
        if acc is None:
            # 全部在冷却，睡到最早恢复
            wake = min(a["available_at"] for a in accounts)
            nap = max(5, min(wake - now, 120))
            log(state_dir, f"[等待] 所有号冷却中，{nap:.0f}s 后重试 (队列剩 {len(queue)})")
            time.sleep(nap)
            continue

        unit = queue.popleft()
        meta = run_one_term(acc, unit["keyword"], args.count, out_videos,
                            args.region_policy, args.phase)
        rc = meta.get("result_class") or "failed"

        if rc == "failed":
            # 限流/技术噪声：号进惩罚冷却，term 重新入队（不丢，不当 zero）
            acc["available_at"] = time.time() + RATELIMIT_COOLDOWN
            acc["burst_count"] = 0
            unit["retries"] += 1
            if unit["retries"] <= MAX_TERM_RETRIES:
                queue.append(unit)
                counts["retry"] += 1
                log(state_dir, f"[限流] {acc['account_id']} 采 #{unit['project_id']}/{unit['keyword']} "
                               f"失败→号冷却{RATELIMIT_COOLDOWN}s, term重入队(第{unit['retries']}次)")
            else:
                # 重采到上限仍失败：最终标 unresolved_failed，绝不当 zero_real
                rec = {**unit, **meta, "result_class": "unresolved_failed",
                       "collector_account": acc["account_id"], "proxy_exit_ip": acc["exit_ip"]}
                terms_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); terms_f.flush()
                counts["unresolved_failed"] += 1; done += 1
                log(state_dir, f"[放弃] #{unit['project_id']}/{unit['keyword']} 重采{MAX_TERM_RETRIES}次仍限流"
                               f"→标 unresolved_failed (绝不计入低传播)")
        else:
            # has_data 或 zero_real：真实结论，记录
            acc["burst_count"] += 1
            rec = {**unit, **meta,
                   "collector_account": acc["account_id"], "proxy_exit_ip": acc["exit_ip"],
                   "proxy_subregion": acc["proxy_subregion"]}
            terms_f.write(json.dumps(rec, ensure_ascii=False) + "\n"); terms_f.flush()
            counts[rc] = counts.get(rc, 0) + 1; done += 1
            log(state_dir, f"[{rc}] {acc['account_id']} #{unit['project_id']}/{unit['keyword']} "
                           f"→ {meta.get('collected_count')}条 {meta.get('depth_verdict')} "
                           f"(进度 {done}/{total_units}, 队列剩{len(queue)})")
            # 预防性轮换：连续成功够 burst 就主动冷却换号
            if acc["burst_count"] >= TERMS_PER_ACCOUNT_BURST:
                acc["available_at"] = time.time() + PREVENTIVE_COOLDOWN
                acc["burst_count"] = 0
                log(state_dir, f"  [预防轮换] {acc['account_id']} 连成{TERMS_PER_ACCOUNT_BURST}个,主动冷却{PREVENTIVE_COOLDOWN}s")
            else:
                time.sleep(INTER_TERM_DELAY)

        # 写实时状态（可中断恢复 + 给监控看）
        state_file.write_text(json.dumps({
            "run_id": run_id, "updated_at": datetime.now().isoformat(),
            "total_units": total_units, "done": done, "queue_remaining": len(queue),
            "counts": counts,
            "accounts": [{"id": a["account_id"], "available_at": a["available_at"],
                          "cooling": a["available_at"] > time.time(),
                          "burst": a["burst_count"]} for a in accounts],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    terms_f.close()
    log(state_dir, f"=== 完成 === 总{total_units} | has_data={counts['has_data']} "
                   f"zero_real={counts['zero_real']} unresolved_failed={counts['unresolved_failed']} "
                   f"重采次数={counts['retry']}")
    log(state_dir, f"视频数据: {out_videos}")
    log(state_dir, f"term结果: {out_terms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
