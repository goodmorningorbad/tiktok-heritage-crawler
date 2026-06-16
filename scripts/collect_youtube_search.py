#!/usr/bin/env python3
"""Collect YouTube search baseline for UNESCO Chinese ICH terms.

Additive collector: writes derived artifacts only; never mutates TikTok baseline.

Quota model (YouTube Data API v3):
- search.list costs 100 quota per page.
- videos.list costs 1 quota per batch of up to 50 ids.

API key is read from YOUTUBE_API_KEY, GOOGLE_API_KEY, or --api-key-file.
Do not commit secrets.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "youtube_ich_search_terms.v1.json"
DEFAULT_OUT_DIR = ROOT / "data" / "derived" / "youtube_initial"
API_BASE = "https://www.googleapis.com/youtube/v3"
SEARCH_COST = 100
VIDEOS_COST = 1


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_api_keys(args: argparse.Namespace) -> List[str]:
    keys: List[str] = []
    if args.api_key:
        keys.extend(k.strip() for k in args.api_key.split(",") if k.strip())
    if args.api_key_file:
        for line in Path(args.api_key_file).read_text(encoding="utf-8").splitlines():
            key = line.strip()
            if key and not key.startswith("#"):
                keys.append(key)
    for name in ("YOUTUBE_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(name, "").strip()
        if val:
            keys.extend(k.strip() for k in val.split(",") if k.strip())
    # preserve order, de-dupe
    deduped: List[str] = []
    seen: set[str] = set()
    for key in keys:
        if key not in seen:
            deduped.append(key)
            seen.add(key)
    if not deduped:
        raise SystemExit("Missing API key: set YOUTUBE_API_KEY or pass --api-key-file/--api-key")
    return deduped


def request_json(endpoint: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    url = f"{API_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "tiktok-heritage-crawler-youtube/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"raw_body": body}
        err_obj = payload.get("error", {}) if isinstance(payload, dict) else {}
        err = err_obj if isinstance(err_obj, dict) else {}
        reason = ""
        errors = err.get("errors") or []
        if errors and isinstance(errors[0], dict):
            reason = errors[0].get("reason", "")
        raise RuntimeError(
            f"HTTP {e.code} {err.get('status','')} reason={reason} message={err.get('message', body[:500])}"
        ) from e


def iter_terms(config: Dict[str, Any], only_terms: Optional[set[str]], only_projects: Optional[set[str]]) -> Iterable[Tuple[Dict[str, Any], str]]:
    for project in config.get("projects", []):
        pid = str(project.get("id"))
        if only_projects and pid not in only_projects and project.get("name_cn") not in only_projects:
            continue
        for term in project.get("youtube_search_terms", []):
            if only_terms and term.lower() not in only_terms:
                continue
            yield project, term


def parse_stats(stats: Dict[str, Any], key: str) -> Optional[int]:
    val = stats.get(key)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except Exception:
        return None


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def collect_search_for_term(
    api_key: str,
    project: Dict[str, Any],
    term: str,
    *,
    max_pages: int,
    region_code: str,
    order: str,
    delay: float,
    timeout: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], int]:
    videos: List[Dict[str, Any]] = []
    seen: set[str] = set()
    next_page_token = ""
    pages_fetched = 0
    search_calls = 0
    total_results_estimate: Optional[int] = None
    stop_reason = "max_pages"
    error_message = ""

    for page_index in range(1, max_pages + 1):
        params: Dict[str, Any] = {
            "part": "snippet",
            "q": term,
            "type": "video",
            "maxResults": 50,
            "regionCode": region_code,
            "order": order,
            "key": api_key,
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        try:
            data = request_json("search", params, timeout=timeout)
        except Exception as e:
            stop_reason = "failed"
            error_message = str(e)
            break
        search_calls += 1
        pages_fetched += 1
        page_info = data.get("pageInfo") or {}
        if total_results_estimate is None:
            total_results_estimate = page_info.get("totalResults")
        items = data.get("items") or []
        page_video_ids: List[str] = []
        for item in items:
            vid = (item.get("id") or {}).get("videoId")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            page_video_ids.append(vid)
            snippet = item.get("snippet") or {}
            videos.append(
                {
                    "video_id": vid,
                    "url": video_url(vid),
                    "source_platform": "youtube",
                    "search_keyword": term,
                    "project_id": project.get("id"),
                    "heritage_item": project.get("name_cn"),
                    "project_name_en": project.get("name_en"),
                    "category": project.get("category"),
                    "search_order": order,
                    "region_code": region_code,
                    "search_rank_within_term": len(videos),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "publishDate": snippet.get("publishedAt", ""),
                    "channelId": snippet.get("channelId", ""),
                    "channelTitle": snippet.get("channelTitle", ""),
                    "thumbnail_default": ((snippet.get("thumbnails") or {}).get("default") or {}).get("url", ""),
                    "tags": [],
                    "viewCount": None,
                    "likeCount": None,
                    "commentCount": None,
                    "duration": "",
                    "definition": "",
                    "caption": "",
                    "licensedContent": None,
                }
            )
        next_page_token = data.get("nextPageToken") or ""
        if not next_page_token:
            stop_reason = "exhausted"
            break
        if delay:
            time.sleep(delay)
    else:
        # If max_pages is below the API-visible 500-ish cap, this is our sampling cap, not a platform ceiling.
        if next_page_token:
            stop_reason = "ceiling_capped_500" if max_pages >= 10 else "sample_limit_reached"
        else:
            stop_reason = "exhausted"

    if not videos and stop_reason != "failed":
        stop_reason = "zero_real"
    elif stop_reason == "max_pages":
        if next_page_token:
            stop_reason = "ceiling_capped_500" if max_pages >= 10 else "sample_limit_reached"
        else:
            stop_reason = "exhausted"

    meta = {
        "project_id": project.get("id"),
        "heritage_item": project.get("name_cn"),
        "project_name_en": project.get("name_en"),
        "category": project.get("category"),
        "search_keyword": term,
        "source_platform": "youtube",
        "region_code": region_code,
        "search_order": order,
        "max_pages_requested": max_pages,
        "pages_fetched": pages_fetched,
        "search_calls": search_calls,
        "search_quota_cost": search_calls * SEARCH_COST,
        "collected_count": len(videos),
        "unique_video_count": len(seen),
        "totalResults_estimate": total_results_estimate,
        "nextPageToken_present_at_stop": bool(next_page_token),
        "stop_reason": stop_reason,
        "error_message": error_message,
        "started_or_recorded_at": now_iso(),
    }
    return videos, meta, search_calls


def enrich_videos(api_key: str, videos: List[Dict[str, Any]], *, timeout: int) -> Tuple[int, int]:
    """Populate statistics/snippet detail in-place. Returns (calls, quota)."""
    by_id: Dict[str, List[Dict[str, Any]]] = {}
    for row in videos:
        by_id.setdefault(row["video_id"], []).append(row)
    ids = list(by_id)
    calls = 0
    for i in range(0, len(ids), 50):
        batch = ids[i : i + 50]
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch),
            "key": api_key,
        }
        data = request_json("videos", params, timeout=timeout)
        calls += 1
        for item in data.get("items") or []:
            vid = item.get("id")
            if not vid or vid not in by_id:
                continue
            snippet = item.get("snippet") or {}
            stats = item.get("statistics") or {}
            details = item.get("contentDetails") or {}
            for row in by_id[vid]:
                # Prefer videos.list full snippet over search snippet when available.
                row["title"] = snippet.get("title", row.get("title", ""))
                row["description"] = snippet.get("description", row.get("description", ""))
                row["publishDate"] = snippet.get("publishedAt", row.get("publishDate", ""))
                row["channelId"] = snippet.get("channelId", row.get("channelId", ""))
                row["channelTitle"] = snippet.get("channelTitle", row.get("channelTitle", ""))
                row["tags"] = snippet.get("tags", [])
                row["viewCount"] = parse_stats(stats, "viewCount")
                row["likeCount"] = parse_stats(stats, "likeCount")
                row["commentCount"] = parse_stats(stats, "commentCount")
                row["duration"] = details.get("duration", "")
                row["definition"] = details.get("definition", "")
                row["caption"] = details.get("caption", "")
                row["licensedContent"] = details.get("licensedContent")
    return calls, calls * VIDEOS_COST


def write_ndjson(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            out = dict(row)
            if isinstance(out.get("tags"), list):
                out["tags"] = "|".join(out["tags"])
            w.writerow(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--api-key", default="", help="Avoid in shell history; prefer env/file.")
    ap.add_argument("--api-key-file", default="")
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--region-code", default="US")
    ap.add_argument("--order", default="relevance", choices=["relevance", "date", "rating", "title", "videoCount", "viewCount"])
    ap.add_argument("--delay", type=float, default=0.05)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--only-term", action="append", default=[], help="Case-insensitive exact term; repeatable")
    ap.add_argument("--only-project", action="append", default=[], help="Project id or Chinese name; repeatable")
    ap.add_argument("--skip-video-details", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_keys = [] if args.dry_run else load_api_keys(args)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    only_terms = {t.lower() for t in args.only_term} if args.only_term else None
    only_projects = set(args.only_project) if args.only_project else None
    term_pairs = list(iter_terms(config, only_terms, only_projects))
    est_search_calls = len(term_pairs) * args.max_pages
    est_quota = est_search_calls * SEARCH_COST + est_search_calls * VIDEOS_COST
    if args.dry_run:
        print(json.dumps({
            "terms": len(term_pairs),
            "max_pages": args.max_pages,
            "estimated_search_calls_upper_bound": est_search_calls,
            "estimated_quota_upper_bound_with_videos_list": est_quota,
        }, ensure_ascii=False, indent=2))
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_videos: List[Dict[str, Any]] = []
    term_meta: List[Dict[str, Any]] = []
    total_search_calls = 0

    print(f"Collecting YouTube: terms={len(term_pairs)} max_pages={args.max_pages} region={args.region_code} order={args.order}", flush=True)
    for idx, (project, term) in enumerate(term_pairs, 1):
        print(f"[{idx}/{len(term_pairs)}] project={project.get('id')} {project.get('name_cn')} term={term!r}", flush=True)
        start_key_index = (idx - 1) % len(api_keys)
        attempts: List[int] = []
        videos: List[Dict[str, Any]] = []
        meta: Dict[str, Any] = {}
        calls = 0
        total_calls_for_term = 0
        for attempt_offset in range(len(api_keys)):
            api_key_index = (start_key_index + attempt_offset) % len(api_keys)
            attempts.append(api_key_index + 1)
            videos, meta, calls = collect_search_for_term(
                api_keys[api_key_index],
                project,
                term,
                max_pages=args.max_pages,
                region_code=args.region_code,
                order=args.order,
                delay=args.delay,
                timeout=args.timeout,
            )
            total_calls_for_term += calls
            meta["api_key_index"] = api_key_index + 1
            meta["api_key_attempts"] = attempts[:]
            if meta.get("stop_reason") != "failed":
                break
            if attempt_offset + 1 < len(api_keys):
                print(f"  !! failed on key#{api_key_index + 1}; retrying with next key", flush=True)
        meta["search_calls_including_failed_attempts"] = total_calls_for_term
        meta["search_quota_cost_including_failed_attempts"] = total_calls_for_term * SEARCH_COST
        total_search_calls += total_calls_for_term
        all_videos.extend(videos)
        term_meta.append(meta)
        print(f"  -> {meta['stop_reason']} videos={meta['collected_count']} totalResults≈{meta['totalResults_estimate']} calls={calls}", flush=True)
        # checkpoint after each term
        write_ndjson(out_dir / "youtube_search_term_meta.ndjson", term_meta)
        write_ndjson(out_dir / "youtube_videos.ndjson", all_videos)

    detail_calls = 0
    detail_quota = 0
    if not args.skip_video_details and all_videos:
        print(f"Enriching videos via videos.list unique_ids={len({v['video_id'] for v in all_videos})}", flush=True)
        # Use the first key for low-cost videos.list enrichment. Search quota is the expensive part.
        detail_calls, detail_quota = enrich_videos(api_keys[0], all_videos, timeout=args.timeout)

    # de-dupe within project and globally for helper summaries, but keep per-search rows in main output.
    summary = {
        "source_platform": "youtube",
        "created_at": now_iso(),
        "config": str(Path(args.config).relative_to(ROOT) if Path(args.config).is_absolute() and ROOT in Path(args.config).parents else args.config),
        "out_dir": str(out_dir),
        "terms_requested": len(term_pairs),
        "max_pages": args.max_pages,
        "region_code": args.region_code,
        "order": args.order,
        "api_keys_loaded": len(api_keys),
        "search_calls": total_search_calls,
        "search_quota_cost": total_search_calls * SEARCH_COST,
        "videos_list_calls": detail_calls,
        "videos_list_quota_cost": detail_quota,
        "total_quota_cost_estimate": total_search_calls * SEARCH_COST + detail_quota,
        "video_rows": len(all_videos),
        "video_rows_with_viewCount": sum(1 for v in all_videos if v.get("viewCount") is not None),
        "unique_video_ids_global": len({v["video_id"] for v in all_videos}),
        "term_stop_reason_counts": {},
    }
    for m in term_meta:
        summary["term_stop_reason_counts"][m["stop_reason"]] = summary["term_stop_reason_counts"].get(m["stop_reason"], 0) + 1

    video_fields = [
        "video_id", "url", "source_platform", "search_keyword", "project_id", "heritage_item", "project_name_en", "category",
        "search_order", "region_code", "search_rank_within_term", "title", "description", "tags", "publishDate",
        "viewCount", "likeCount", "commentCount", "channelId", "channelTitle", "duration", "definition", "caption", "licensedContent",
        "thumbnail_default",
    ]
    meta_fields = [
        "project_id", "heritage_item", "project_name_en", "category", "search_keyword", "source_platform", "region_code", "search_order",
        "api_key_index", "api_key_attempts", "search_calls_including_failed_attempts", "search_quota_cost_including_failed_attempts",
        "max_pages_requested", "pages_fetched", "search_calls", "search_quota_cost", "collected_count", "unique_video_count",
        "totalResults_estimate", "nextPageToken_present_at_stop", "stop_reason", "error_message", "started_or_recorded_at",
    ]
    write_ndjson(out_dir / "youtube_videos.ndjson", all_videos)
    write_ndjson(out_dir / "youtube_search_term_meta.ndjson", term_meta)
    write_csv(out_dir / "youtube_videos.csv", all_videos, video_fields)
    write_csv(out_dir / "youtube_search_term_meta.csv", term_meta, meta_fields)
    (out_dir / "youtube_collection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
