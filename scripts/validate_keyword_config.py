#!/usr/bin/env python3
"""Validate keyword config for collection/labeling.

This check is deterministic and does not call TikTok.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_PROJECT_FIELDS = {
    "id",
    "name_cn",
    "name_en",
    "year",
    "category",
    "search_terms",
    "core_terms",
    "negative_terms",
    "hashtag_terms",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/unesco_ich_keywords.v1.json")
    ap.add_argument("--expected-project-count", type=int, default=None)
    args = ap.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"ERROR: config not found: {path}", file=sys.stderr)
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("negative_terms_policy") != "label_only_never_exclude":
        errors.append("negative_terms_policy must be label_only_never_exclude")
    projects = data.get("projects") or []
    expected = args.expected_project_count or data.get("expected_project_count")
    if expected and len(projects) != int(expected):
        warnings.append(f"expected {expected} projects, found {len(projects)}")

    seen_ids = set()
    seen_names = set()
    for idx, project in enumerate(projects, start=1):
        missing = sorted(REQUIRED_PROJECT_FIELDS - set(project))
        if missing:
            errors.append(f"project #{idx} missing fields: {missing}")
        pid = project.get("id")
        name = project.get("name_cn")
        if pid in seen_ids:
            errors.append(f"duplicate project id: {pid}")
        if name in seen_names:
            errors.append(f"duplicate project name_cn: {name}")
        seen_ids.add(pid)
        seen_names.add(name)
        if not project.get("search_terms"):
            errors.append(f"{name}: search_terms is empty")
        if not project.get("core_terms"):
            errors.append(f"{name}: core_terms is empty")
        for field in ["search_terms", "core_terms", "negative_terms", "hashtag_terms"]:
            value = project.get(field)
            if not isinstance(value, list):
                errors.append(f"{name}: {field} must be a list")

    report = {
        "config": str(path),
        "version": data.get("version"),
        "projects": len(projects),
        "expected_project_count": expected,
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
