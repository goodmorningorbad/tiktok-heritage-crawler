#!/usr/bin/env python3
"""
批量采集 UNESCO 中国非遗项目的 TikTok 数据。
根据 Excel 表中的搜索关键词建议，为每个项目采集视频元数据；不下载视频。
"""
from __future__ import annotations

import csv
import json
import os
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECTS_FILE = Path(os.getenv("PROJECTS_FILE", "/tmp/unesco_projects.json"))
KEYWORD_CONFIG = Path(os.getenv("KEYWORD_CONFIG", "config/unesco_ich_keywords.v1.json"))
WORKDIR = Path("/root/workspace/tiktok-heritage-crawler")
OUTPUT_DIR = WORKDIR / "data"
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
PER_PROJECT_DIR = OUTPUT_DIR / f"run_{RUN_ID}_projects"
COMBINED_NDJSON = OUTPUT_DIR / f"unesco_tiktok_{RUN_ID}.ndjson"
COMBINED_CSV = OUTPUT_DIR / f"unesco_tiktok_{RUN_ID}.csv"
REPORT_FILE = OUTPUT_DIR / f"collection_report_{RUN_ID}.json"
VIDEOS_PER_KEYWORD = int(os.getenv("VIDEOS_PER_KEYWORD", "20"))
RUN_CHANNELS = os.getenv("RUN_CHANNELS", os.getenv("RUN_MODE", "search")).lower()
TIMEOUT_PER_PROJECT = int(os.getenv("TIMEOUT_PER_PROJECT", "360"))

DROP_FIELDS = {"raw"}
PROJECT_FIELDS = ["heritage_id", "heritage_name_cn", "heritage_name_en", "heritage_year", "heritage_category"]


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else WORKDIR / path


def load_projects(projects_file: Path | None = None, keyword_config: Path | None = None) -> list[dict]:
    cfg_path = resolve_path(keyword_config or KEYWORD_CONFIG)
    if cfg_path.exists():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        projects = []
        for item in data.get("projects", []):
            projects.append({
                "id": item["id"],
                "name_cn": item["name_cn"],
                "name_en": item.get("name_en", ""),
                "year": item.get("year", ""),
                "category": item.get("category", ""),
                "search_terms": item.get("search_terms", []),
                "hashtag_terms": item.get("hashtag_terms", []),
            })
        return projects

    proj_path = resolve_path(projects_file or PROJECTS_FILE)
    if not proj_path.exists():
        raise SystemExit(f"找不到项目列表文件或关键词配置: {proj_path} / {cfg_path}")
    return json.loads(proj_path.read_text(encoding="utf-8"))


def keywords_to_csv(value: str) -> str:
    return value.replace("#", "").replace(" / ", ",").replace("/", ",")


def terms_to_csv(value) -> str:
    if isinstance(value, str):
        return keywords_to_csv(value)
    return ",".join(str(x).strip().lstrip("#") for x in (value or []) if str(x).strip())


def parse_channels(value: str) -> list[str]:
    value = (value or "search").lower().strip()
    if value == "both":
        return ["search", "hashtag"]
    channels = [x.strip() for x in value.split(",") if x.strip()]
    bad = [x for x in channels if x not in {"search", "hashtag"}]
    if bad:
        raise SystemExit(f"未知 channel: {bad}; use search, hashtag, or both")
    return channels or ["search"]


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def collector_context(env: dict) -> dict:
    return {
        "collector_account": env.get("TIKTOK_ACCOUNT_ID", ""),
        "collector_account_role": env.get("TIKTOK_ACCOUNT_ROLE", "neutral"),
        "proxy_region": env.get("TIKTOK_PROXY_REGION", "unknown"),
        "proxy_subregion": env.get("TIKTOK_PROXY_SUBREGION", ""),
        "proxy_pool": env.get("TIKTOK_PROXY_POOL", ""),
        "proxy_id": env.get("TIKTOK_PROXY_ID", ""),
        "proxy_exit_ip": env.get("TIKTOK_PROXY_EXIT_IP", ""),
        "proxy_isp": env.get("TIKTOK_PROXY_ISP", ""),
    }


def parse_search_meta(stderr: str) -> list[dict]:
    metas: list[dict] = []
    for line in (stderr or "").splitlines():
        if not line.startswith("SEARCH_META "):
            continue
        try:
            metas.append(json.loads(line.split(" ", 1)[1]))
        except json.JSONDecodeError:
            metas.append({"parse_error": line})
    return metas


def append_enriched_rows(src: Path, project: dict, seen_ids: set[str], combined_f, matched_sources: dict[str, set[str]]) -> tuple[int, int]:
    total = 0
    new = 0
    if not src.exists():
        return total, new
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            row = json.loads(line)
            vid = row.get("id") or f"noid:{project['id']}:{total}"
            source = row.get("source") or ""
            matched_sources.setdefault(vid, set()).add(str(source))
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            row.update({
                "heritage_id": project["id"],
                "heritage_name_cn": project["name_cn"],
                "heritage_name_en": project.get("name_en", ""),
                "heritage_year": project.get("year", ""),
                "heritage_category": project.get("category", ""),
                "source_channel": row.get("source_type", ""),
                "search_keyword": source,
            })
            row["matched_sources"] = sorted(matched_sources.get(vid, {str(source)}))
            combined_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            new += 1
    return total, new


def ndjson_to_csv(src: Path, dst: Path) -> int:
    rows = []
    fields = []
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            flat = {
                k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                for k, v in row.items()
                if k not in DROP_FIELDS
            }
            # 项目信息放到前面
            ordered = {k: flat.pop(k) for k in PROJECT_FIELDS if k in flat}
            ordered.update(flat)
            flat = ordered
            rows.append(flat)
            for key in flat.keys():
                if key not in fields:
                    fields.append(key)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def run_channel(project: dict, channel: str, terms_csv: str, out: Path, env: dict) -> tuple[dict, subprocess.CompletedProcess | None]:
    cmd = [sys.executable, "crawler.py", channel]
    if channel == "search":
        cmd.extend(["--keywords", terms_csv])
    else:
        cmd.extend(["--hashtags", terms_csv])
    cmd.extend(["--count", str(VIDEOS_PER_KEYWORD), "--out", str(out)])

    started = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(WORKDIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_PER_PROJECT,
        )
        elapsed = round(time.time() - started, 1)
        status = "ok" if result.returncode == 0 else "failed"
        if result.returncode == 0 and "HASHTAG_FAILED" in result.stderr:
            status = "partial"
        search_meta = parse_search_meta(result.stderr) if channel == "search" else []
        item = {
            "channel": channel,
            "terms": terms_csv.split(",") if terms_csv else [],
            "status": status,
            "returncode": result.returncode,
            "elapsed_sec": elapsed,
            "collector": collector_context(env),
            "search_terms_meta": search_meta,
            "search_hit_cap_terms": [m.get("keyword") for m in search_meta if m.get("hit_cap")],
            "search_has_more_at_stop": any(bool(m.get("has_more_at_stop")) for m in search_meta),
            "stdout_tail": result.stdout[-1000:],
            "stderr_tail": result.stderr[-2000:],
            "out": str(out),
        }
        return item, result
    except subprocess.TimeoutExpired as e:
        elapsed = round(time.time() - started, 1)
        return {
            "channel": channel,
            "terms": terms_csv.split(",") if terms_csv else [],
            "status": "timeout",
            "elapsed_sec": elapsed,
            "out": str(out),
            "collector": collector_context(env),
            "error": str(e),
        }, None
    except Exception as e:
        return {
            "channel": channel,
            "terms": terms_csv.split(",") if terms_csv else [],
            "status": "exception",
            "out": str(out),
            "collector": collector_context(env),
            "error": repr(e),
        }, None


def main(argv: list[str] | None = None) -> None:
    global VIDEOS_PER_KEYWORD
    ap = argparse.ArgumentParser(description="批量采集 UNESCO 中国非遗 TikTok 数据")
    ap.add_argument("--keyword-config", default=str(KEYWORD_CONFIG), help="关键词配置 JSON；优先于 PROJECTS_FILE")
    ap.add_argument("--projects-file", default=str(PROJECTS_FILE), help="旧版项目 JSON fallback")
    ap.add_argument("--channels", default=RUN_CHANNELS, help="search, hashtag, or both")
    ap.add_argument("--videos-per-term", type=int, default=VIDEOS_PER_KEYWORD)
    ap.add_argument("--limit-projects", type=int, default=0, help="仅跑前 N 个项目，用于 smoke test")
    args = ap.parse_args(argv)

    VIDEOS_PER_KEYWORD = args.videos_per_term
    channels = parse_channels(args.channels)
    projects = load_projects(Path(args.projects_file), Path(args.keyword_config))
    if args.limit_projects:
        projects = projects[: args.limit_projects]

    OUTPUT_DIR.mkdir(exist_ok=True)
    PER_PROJECT_DIR.mkdir(exist_ok=True)

    print(f"开始批量采集 {len(projects)} 个非遗项目")
    print(f"channels={channels}; 每个 term {VIDEOS_PER_KEYWORD} 条；输出: {COMBINED_CSV}")
    print("=" * 72, flush=True)

    env = os.environ.copy()
    env.setdefault("TIKTOK_COOKIES_JSON", str(WORKDIR / "cookies.json"))
    env.setdefault("TIKTOK_BROWSER", "chromium")
    env.setdefault("TIKTOK_TIMEOUT_MS", "90000")

    report = {
        "run_id": RUN_ID,
        "started_at": datetime.now().isoformat(),
        "videos_per_term": VIDEOS_PER_KEYWORD,
        "channels": channels,
        "collection_phase": os.getenv("COLLECTION_PHASE", "unspecified"),
        "region_policy": os.getenv("TIKTOK_REGION_POLICY", "single-region-baseline"),
        "collector": collector_context(env),
        "keyword_config": str(resolve_path(Path(args.keyword_config))),
        "projects": [],
    }
    seen_ids: set[str] = set()
    matched_sources: dict[str, set[str]] = {}
    total_new = 0

    with COMBINED_NDJSON.open("w", encoding="utf-8") as combined_f:
        for idx, project in enumerate(projects, start=1):
            name_cn = project["name_cn"]
            item = {"id": project["id"], "name_cn": name_cn, "channels": []}
            print(f"\n[{idx}/{len(projects)}] #{project['id']} {name_cn}", flush=True)

            for channel in channels:
                term_key = "search_terms" if channel == "search" else "hashtag_terms"
                terms_csv = terms_to_csv(project.get(term_key) or project.get("keywords") or "")
                channel_item = {"channel": channel, "terms": terms_csv.split(",") if terms_csv else []}
                if not terms_csv.strip():
                    channel_item.update({"status": "skipped", "reason": f"no {term_key}", "rows_total": 0, "rows_new": 0, "sample_rows_total": 0, "total_results": 0, "total_results_note": "deprecated: sampled rows only, not platform total"})
                    item["channels"].append(channel_item)
                    print(f"  跳过 {channel}: 无 {term_key}", flush=True)
                    continue

                out = PER_PROJECT_DIR / f"{project['id']:02d}_{name_cn}_{channel}.ndjson"
                if out.exists():
                    out.unlink()
                print(f"  {channel}: {terms_csv}", flush=True)

                channel_item, _ = run_channel(project, channel, terms_csv, out, env)
                rows_total, rows_new = append_enriched_rows(out, project, seen_ids, combined_f, matched_sources)
                total_new += rows_new
                channel_item.update({
                    "rows_total": rows_total,
                    "rows_new": rows_new,
                    "sample_rows_total": rows_total,
                    "total_results": rows_total,
                    "total_results_note": "deprecated: sampled rows only, not platform total",
                })
                item["channels"].append(channel_item)
                mark = "✓" if channel_item.get("status") == "ok" else "✗"
                print(f"  {mark} {channel} 原始 {rows_total} 条，去重新增 {rows_new} 条，用时 {channel_item.get('elapsed_sec', 0)}s", flush=True)
                if channel_item.get("status") not in ("ok", "skipped"):
                    print(f"  错误: {(channel_item.get('stderr_tail') or channel_item.get('stdout_tail') or channel_item.get('error') or '')[-500:]}", flush=True)

            report["projects"].append(item)
            REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_rows = ndjson_to_csv(COMBINED_NDJSON, COMBINED_CSV)
    ok_channels = 0
    partial_channels = 0
    failed_channels = 0
    for p in report["projects"]:
        for c in p.get("channels", []):
            if c.get("status") == "ok":
                ok_channels += 1
            elif c.get("status") == "partial":
                partial_channels += 1
            elif c.get("status") != "skipped":
                failed_channels += 1
    report.update({
        "finished_at": datetime.now().isoformat(),
        "combined_ndjson": str(COMBINED_NDJSON),
        "combined_csv": str(COMBINED_CSV),
        "total_unique_rows": total_new,
        "csv_rows": csv_rows,
        "ok_channels": ok_channels,
        "partial_channels": partial_channels,
        "failed_channels": failed_channels,
    })
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 72)
    print(f"完成：唯一视频 {total_new} 条")
    print(f"CSV: {COMBINED_CSV}")
    print(f"报告: {REPORT_FILE}")


if __name__ == "__main__":
    main()
