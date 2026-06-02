#!/usr/bin/env python3
"""Run or preview the TikTok second-test collection plan.

Dry-run is deterministic and does not call TikTok. Real runs delegate to
batch_collect.py so Hermes/Morn owns the long process.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "unesco_ich_keywords.v1.json"


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def print_plan(config: dict, channels: list[str], limit_projects: int = 0) -> None:
    projects = config.get("projects", [])
    if limit_projects:
        projects = projects[:limit_projects]
    print(json.dumps({
        "config_version": config.get("version"),
        "negative_terms_policy": config.get("negative_terms_policy"),
        "project_count": len(projects),
        "expected_project_count": config.get("expected_project_count"),
        "channels": channels,
    }, ensure_ascii=False, indent=2))
    for p in projects:
        print(f"#{p['id']:02d} {p['name_cn']}")
        if "search" in channels:
            print("  search_terms:", ", ".join(p.get("search_terms") or []))
        if "hashtag" in channels:
            print("  hashtag_terms:", ", ".join(p.get("hashtag_terms") or []))


def parse_channels(value: str) -> list[str]:
    value = value.lower().strip()
    if value == "both":
        return ["search", "hashtag"]
    channels = [x.strip() for x in value.split(",") if x.strip()]
    bad = [x for x in channels if x not in {"search", "hashtag"}]
    if bad:
        raise SystemExit(f"unknown channel(s): {bad}")
    return channels or ["search"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Preview or run second-test TikTok collection")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--channels", default="both", help="search, hashtag, or both")
    ap.add_argument("--videos-per-term", type=int, default=30)
    ap.add_argument("--limit-projects", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config_path = Path(args.config)
    channels = parse_channels(args.channels)
    config = load_config(config_path)
    if args.dry_run:
        print_plan(config, channels, args.limit_projects)
        return 0

    cmd = [
        sys.executable,
        "batch_collect.py",
        "--keyword-config", str(config_path),
        "--channels", args.channels,
        "--videos-per-term", str(args.videos_per_term),
    ]
    if args.limit_projects:
        cmd.extend(["--limit-projects", str(args.limit_projects)])
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
