#!/usr/bin/env python3
"""
TikTok 采集 账号×IP pool runner
================================

职责：把 N 个非遗项目按「账号×住宅IP」固定分配，每个分片用钉死的
(account, cookie, proxy_port, region) 组合调用 batch_collect.py，
并把真实来源元数据 (collector_account / proxy_id / proxy_region /
exit_ip / isp) 写进每条数据和 report。

设计原则（对应交接文档「账号/IP pool runner」需求）：
- 输入：pool 定义文件（账号列表 + 住宅IP端口列表）。
- 每个项目固定分配一个 (账号, IP) slot；同一轮保持统一 region。
- assignment 写入 manifest，保证可追溯，绝不混采不可溯源。
- 单一 region baseline：本 runner 只跑 US 住宅池，不混 region。
- 不碰 turn-proxy 既有 :1090/:1091；采集走独立 :1092+ US-only 实例。

用法：
    # dry-run：只打印分配方案，不采集
    python3 pool_runner.py --dry-run --channels both --videos-per-term 30

    # 真跑：每分片单独起 batch_collect，结果合并
    python3 pool_runner.py --channels search --videos-per-term 2000

分配策略 --assign：
    round-robin（默认）：项目轮流分给各 slot，负载均衡。
    chunk：连续切块，每个 slot 拿一段连续项目。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "unesco_ich_keywords.v1.json"
DEFAULT_POOL = ROOT / "config" / "us_pool.json"
DATA_DIR = ROOT / "data"
# TikTokApi 装在专用 venv；runner 必须用它起 batch_collect，否则子进程 ModuleNotFoundError
DEFAULT_PYTHON = "/root/workspace/tiktok-api-venv/bin/python3"


def load_json(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def build_slots(pool: dict) -> list[dict]:
    """把 pool 定义展开成可用 slot 列表。每个 slot = 一个账号绑一个 IP 端口。"""
    accounts = pool["accounts"]          # [{id, role, cookies}]
    proxies = pool["proxies"]            # [{proxy_id, socks, exit_ip, isp, region, subregion, pool}]
    n = min(len(accounts), len(proxies))
    if n == 0:
        raise SystemExit("pool 里账号或代理为空")
    slots = []
    for i in range(n):
        a = accounts[i]
        x = proxies[i]
        slots.append({
            "slot": i + 1,
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
        })
    return slots


def assign_projects(projects: list[dict], slots: list[dict], mode: str) -> dict[int, list[dict]]:
    """返回 {slot_index: [projects...]}。"""
    buckets: dict[int, list[dict]] = {i: [] for i in range(len(slots))}
    if mode == "chunk":
        per = (len(projects) + len(slots) - 1) // len(slots)
        for si in range(len(slots)):
            buckets[si] = projects[si * per:(si + 1) * per]
    else:  # round-robin
        for pi, proj in enumerate(projects):
            buckets[pi % len(slots)].append(proj)
    return buckets


def slot_env(slot: dict, region_policy: str, phase: str) -> dict:
    env = os.environ.copy()
    env["TIKTOK_COOKIES_JSON"] = slot["cookies"]
    env["HTTPS_PROXY"] = slot["socks"]
    env["HTTP_PROXY"] = slot["socks"]
    # 真实来源元数据，batch_collect.collector_context() 会读这些写进每条数据
    env["TIKTOK_ACCOUNT_ID"] = slot["account_id"]
    env["TIKTOK_ACCOUNT_ROLE"] = slot["account_role"]
    env["TIKTOK_PROXY_REGION"] = slot["proxy_region"]
    env["TIKTOK_PROXY_SUBREGION"] = slot["proxy_subregion"]
    env["TIKTOK_PROXY_POOL"] = slot["proxy_pool"]
    env["TIKTOK_PROXY_ID"] = slot["proxy_id"]
    env["TIKTOK_PROXY_EXIT_IP"] = slot["exit_ip"]
    env["TIKTOK_PROXY_ISP"] = slot["isp"]
    env["TIKTOK_REGION_POLICY"] = region_policy
    env["COLLECTION_PHASE"] = phase
    env.setdefault("TIKTOK_TIMEOUT_MS", "90000")
    return env


def write_slot_project_config(base_cfg: dict, projects: list[dict], dst: Path) -> None:
    """为某 slot 写一个只含其分到的项目的临时 keyword config。"""
    sub = dict(base_cfg)
    ids = {p["id"] for p in projects}
    sub["projects"] = [p for p in base_cfg["projects"] if p["id"] in ids]
    dst.write_text(json.dumps(sub, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="TikTok 账号×IP pool runner (US residential baseline)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--pool", default=str(DEFAULT_POOL))
    ap.add_argument("--channels", default="both", help="search, hashtag, or both")
    ap.add_argument("--videos-per-term", type=int, default=30)
    ap.add_argument("--limit-projects", type=int, default=0)
    ap.add_argument("--assign", choices=["round-robin", "chunk"], default="round-robin")
    ap.add_argument("--phase", default="pilot")
    ap.add_argument("--region-policy", default="single-region-baseline")
    ap.add_argument("--python", default=DEFAULT_PYTHON,
                    help="跑 batch_collect 的 python（须能 import TikTokApi）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headful", action="store_true",
                    help="用 xvfb-run + TIKTOK_HEADLESS=false（hashtag 通道推荐）")
    args = ap.parse_args()

    base_cfg = load_json(Path(args.config))
    pool = load_json(Path(args.pool))
    projects = list(base_cfg.get("projects", []))
    if args.limit_projects:
        projects = projects[: args.limit_projects]

    slots = build_slots(pool)
    buckets = assign_projects(projects, slots, args.assign)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "channels": args.channels,
        "videos_per_term": args.videos_per_term,
        "assign_mode": args.assign,
        "region_policy": args.region_policy,
        "phase": args.phase,
        "pool_region": pool.get("region", "US"),
        "slots": [],
    }

    print(f"=== TikTok pool runner | run_id={run_id} ===")
    print(f"region={pool.get('region','US')} policy={args.region_policy} "
          f"channels={args.channels} per_term={args.videos_per_term} assign={args.assign}")
    print(f"projects={len(projects)} slots={len(slots)}\n")

    for si, slot in enumerate(slots):
        ps = buckets[si]
        print(f"slot{slot['slot']}: {slot['account_id']} @ {slot['proxy_id']} "
              f"({slot['exit_ip']} {slot['proxy_subregion']} {slot['isp'][:18]}) "
              f"<- {len(ps)} 项: {[p['id'] for p in ps]}")
        manifest["slots"].append({
            **{k: slot[k] for k in ("slot", "account_id", "account_role", "proxy_id",
                                    "socks", "exit_ip", "isp", "proxy_region",
                                    "proxy_subregion", "proxy_pool")},
            "project_ids": [p["id"] for p in ps],
            "project_count": len(ps),
        })

    manifest_path = DATA_DIR / f"pool_manifest_{run_id}.json"
    DATA_DIR.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nmanifest: {manifest_path}")

    if args.dry_run:
        print("\n[dry-run] 不采集，仅输出分配方案。")
        return 0

    # 真跑：每个 slot 独立起 batch_collect，钉死 env
    slot_results = []
    tmp_dir = DATA_DIR / f"pool_run_{run_id}_slots"
    tmp_dir.mkdir(exist_ok=True)
    for si, slot in enumerate(slots):
        ps = buckets[si]
        if not ps:
            continue
        sub_cfg = tmp_dir / f"slot{slot['slot']}_config.json"
        write_slot_project_config(base_cfg, ps, sub_cfg)
        env = slot_env(slot, args.region_policy, args.phase)

        if args.headful:
            cmd = ["xvfb-run", "-a", args.python, "batch_collect.py"]
            env["TIKTOK_HEADLESS"] = "false"
        else:
            cmd = [args.python, "batch_collect.py"]
        cmd += ["--keyword-config", str(sub_cfg),
                "--channels", args.channels,
                "--videos-per-term", str(args.videos_per_term)]

        print(f"\n{'='*72}\n>>> slot{slot['slot']} 启动: {slot['account_id']} @ {slot['proxy_id']} "
              f"({slot['exit_ip']}) | {len(ps)} 项\n{'='*72}", flush=True)
        started = time.time()
        rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
        elapsed = round(time.time() - started, 1)
        slot_results.append({"slot": slot["slot"], "account_id": slot["account_id"],
                             "proxy_id": slot["proxy_id"], "returncode": rc,
                             "elapsed_sec": elapsed, "project_count": len(ps)})
        print(f">>> slot{slot['slot']} 结束 rc={rc} 用时 {elapsed}s", flush=True)

    manifest["finished_at"] = datetime.now().isoformat()
    manifest["slot_results"] = slot_results
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 全部 slot 完成 ===\nmanifest: {manifest_path}")
    print("各 slot 的数据/report 在 data/ 下按各自 run_id 命名（每个 batch_collect 独立 run_id）。")
    print("注意：本 runner 每 slot 串行跑（共享 cookie 刷新/避免风控）；如需并行后续可加。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
