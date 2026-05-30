#!/usr/bin/env python3
"""
批量采集 UNESCO 中国非遗项目的 TikTok 数据。
根据 Excel 表中的搜索关键词建议，为每个项目采集视频元数据；不下载视频。
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECTS_FILE = Path(os.getenv("PROJECTS_FILE", "/tmp/unesco_projects.json"))
WORKDIR = Path("/root/workspace/tiktok-heritage-crawler")
OUTPUT_DIR = WORKDIR / "data"
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
PER_PROJECT_DIR = OUTPUT_DIR / f"run_{RUN_ID}_projects"
COMBINED_NDJSON = OUTPUT_DIR / f"unesco_tiktok_{RUN_ID}.ndjson"
COMBINED_CSV = OUTPUT_DIR / f"unesco_tiktok_{RUN_ID}.csv"
REPORT_FILE = OUTPUT_DIR / f"collection_report_{RUN_ID}.json"
VIDEOS_PER_KEYWORD = int(os.getenv("VIDEOS_PER_KEYWORD", "20"))
TIMEOUT_PER_PROJECT = int(os.getenv("TIMEOUT_PER_PROJECT", "360"))

DROP_FIELDS = {"raw"}
PROJECT_FIELDS = ["heritage_id", "heritage_name_cn", "heritage_name_en", "heritage_year", "heritage_category"]


def load_projects() -> list[dict]:
    if not PROJECTS_FILE.exists():
        raise SystemExit(f"找不到项目列表文件: {PROJECTS_FILE}")
    return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))


def keywords_to_csv(value: str) -> str:
    return value.replace("#", "").replace(" / ", ",").replace("/", ",")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def append_enriched_rows(src: Path, project: dict, seen_ids: set[str], combined_f) -> tuple[int, int]:
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
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            row.update({
                "heritage_id": project["id"],
                "heritage_name_cn": project["name_cn"],
                "heritage_name_en": project["name_en"],
                "heritage_year": project["year"],
                "heritage_category": project["category"],
            })
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


def main() -> None:
    projects = load_projects()
    OUTPUT_DIR.mkdir(exist_ok=True)
    PER_PROJECT_DIR.mkdir(exist_ok=True)

    print(f"开始批量采集 {len(projects)} 个非遗项目")
    print(f"每个关键词 {VIDEOS_PER_KEYWORD} 条；输出: {COMBINED_CSV}")
    print("=" * 72, flush=True)

    env = os.environ.copy()
    env.setdefault("TIKTOK_COOKIES_JSON", str(WORKDIR / "cookies.json"))
    env.setdefault("TIKTOK_BROWSER", "chromium")
    env.setdefault("TIKTOK_TIMEOUT_MS", "90000")

    report = {
        "run_id": RUN_ID,
        "started_at": datetime.now().isoformat(),
        "videos_per_keyword": VIDEOS_PER_KEYWORD,
        "projects": [],
    }
    seen_ids: set[str] = set()
    total_new = 0

    with COMBINED_NDJSON.open("w", encoding="utf-8") as combined_f:
        for idx, project in enumerate(projects, start=1):
            name_cn = project["name_cn"]
            keywords = project.get("keywords") or ""
            item = {"id": project["id"], "name_cn": name_cn, "keywords": keywords}

            if not keywords.strip():
                item.update({"status": "skipped", "reason": "no keywords", "rows_total": 0, "rows_new": 0})
                report["projects"].append(item)
                print(f"[{idx}/{len(projects)}] 跳过 #{project['id']} {name_cn}: 无关键词", flush=True)
                continue

            kw = keywords_to_csv(keywords)
            out = PER_PROJECT_DIR / f"{project['id']:02d}_{name_cn}.ndjson"
            if out.exists():
                out.unlink()

            print(f"\n[{idx}/{len(projects)}] #{project['id']} {name_cn}")
            print(f"  关键词: {kw}", flush=True)

            cmd = [
                sys.executable, "crawler.py", "search",
                "--keywords", kw,
                "--count", str(VIDEOS_PER_KEYWORD),
                "--out", str(out),
            ]
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
                rows_total, rows_new = append_enriched_rows(out, project, seen_ids, combined_f)
                total_new += rows_new
                item.update({
                    "status": "ok" if result.returncode == 0 else "failed",
                    "returncode": result.returncode,
                    "elapsed_sec": elapsed,
                    "rows_total": rows_total,
                    "rows_new": rows_new,
                    "stdout_tail": result.stdout[-1000:],
                    "stderr_tail": result.stderr[-2000:],
                    "out": str(out),
                })
                print(f"  {'✓' if result.returncode == 0 else '✗'} 原始 {rows_total} 条，去重新增 {rows_new} 条，用时 {elapsed}s", flush=True)
                if result.returncode != 0:
                    print(f"  错误: {(result.stderr or result.stdout)[-500:]}", flush=True)
            except subprocess.TimeoutExpired as e:
                elapsed = round(time.time() - started, 1)
                rows_total, rows_new = append_enriched_rows(out, project, seen_ids, combined_f)
                total_new += rows_new
                item.update({"status": "timeout", "elapsed_sec": elapsed, "rows_total": rows_total, "rows_new": rows_new, "out": str(out), "error": str(e)})
                print(f"  ✗ 超时；已保留 {rows_total} 条，新增 {rows_new} 条", flush=True)
            except Exception as e:
                item.update({"status": "exception", "error": repr(e), "rows_total": count_lines(out), "rows_new": 0, "out": str(out)})
                print(f"  ✗ 异常: {e}", flush=True)

            report["projects"].append(item)
            REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_rows = ndjson_to_csv(COMBINED_NDJSON, COMBINED_CSV)
    report.update({
        "finished_at": datetime.now().isoformat(),
        "combined_ndjson": str(COMBINED_NDJSON),
        "combined_csv": str(COMBINED_CSV),
        "total_unique_rows": total_new,
        "csv_rows": csv_rows,
        "ok_projects": sum(1 for p in report["projects"] if p.get("status") == "ok"),
        "failed_projects": sum(1 for p in report["projects"] if p.get("status") not in ("ok", "skipped")),
    })
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 72)
    print(f"完成：唯一视频 {total_new} 条")
    print(f"CSV: {COMBINED_CSV}")
    print(f"报告: {REPORT_FILE}")


if __name__ == "__main__":
    main()
