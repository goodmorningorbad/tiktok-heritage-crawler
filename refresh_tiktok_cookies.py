#!/usr/bin/env python3
"""Refresh and export TikTok browser session cookies.

This script uses a persistent Playwright browser profile. After a profile has been
logged in once, future runs can refresh TikTok cookies without manual export.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def normalize_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    out = dict(cookie)
    # Cookie-Editor style compatibility: many existing project scripts accept
    # expirationDate; Playwright exports expires.
    if isinstance(out.get("expires"), (int, float)) and out.get("expires", -1) > 0:
        out["expirationDate"] = int(out["expires"])
    return out


def load_seed_cookies(path: str | None) -> list[dict[str, Any]]:
    """Load browser-exported cookies and convert them to Playwright format."""
    if not path:
        return []
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"cookies-in file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]
    if not isinstance(data, list):
        raise ValueError("cookies-in must be a JSON list or an object with a cookies list")

    cookies: list[dict[str, Any]] = []
    for c in data:
        if not isinstance(c, dict) or not c.get("name") or c.get("value") is None:
            continue
        cookie: dict[str, Any] = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain") or ".tiktok.com",
            "path": c.get("path") or "/",
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        }
        expires = c.get("expires") if c.get("expires") not in (None, -1) else c.get("expirationDate")
        if isinstance(expires, (int, float)) and expires > 0:
            cookie["expires"] = int(expires)
        same_site = c.get("sameSite") or c.get("same_site")
        if same_site:
            same_site = str(same_site).lower().replace("no_restriction", "none")
            cookie["sameSite"] = {"none": "None", "lax": "Lax", "strict": "Strict"}.get(same_site, "None")
        cookies.append(cookie)
    return cookies


async def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh/export TikTok cookies from a persistent browser profile")
    parser.add_argument("--profile-dir", default="profiles/tiktok-default", help="Persistent Chromium profile directory")
    parser.add_argument("--out", default="cookies/auto_tiktok_cookies.json", help="Cookie JSON output path")
    parser.add_argument("--storage-out", default="cookies/auto_tiktok_storage_state.json", help="Playwright storageState output path")
    parser.add_argument("--cookies-in", default=None, help="Seed Playwright profile from an existing exported cookies JSON before refresh")
    parser.add_argument("--proxy", default=os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"), help="Proxy URL, e.g. http://host:port")
    parser.add_argument("--headless", action="store_true", help="Run headless. Use headed for first login on a GUI machine.")
    parser.add_argument("--query", default="chinesenewyear", help="Search query used to warm the session")
    parser.add_argument("--timeout-ms", type=int, default=90000)
    args = parser.parse_args()

    profile_dir = Path(args.profile_dir).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    storage_out = Path(args.storage_out).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    storage_out.parent.mkdir(parents=True, exist_ok=True)

    launch_kwargs: dict[str, Any] = {
        "headless": args.headless,
        "user_agent": DEFAULT_UA,
        "locale": "en-US",
        "viewport": {"width": 1366, "height": 900},
        "ignore_https_errors": True,
    }
    if args.proxy:
        launch_kwargs["proxy"] = {"server": args.proxy}

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(str(profile_dir), **launch_kwargs)
        seed_cookies = load_seed_cookies(args.cookies_in)
        if seed_cookies:
            await context.add_cookies(seed_cookies)
        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(args.timeout_ms)
        status: dict[str, Any] = {
            "profile_dir": str(profile_dir),
            "proxy": args.proxy,
            "headless": args.headless,
            "cookies_in": str(Path(args.cookies_in).expanduser().resolve()) if args.cookies_in else None,
            "seed_cookie_count": len(seed_cookies),
        }

        try:
            await page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(3000)
            status["home_url"] = page.url
            status["home_title"] = await page.title()
        except PlaywrightTimeoutError as e:
            status["home_error"] = f"timeout: {e}"

        try:
            search_url = f"https://www.tiktok.com/search/video?q={args.query}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            await page.wait_for_timeout(8000)
            status["search_url"] = page.url
            status["search_title"] = await page.title()
            body_text = ""
            try:
                body_text = (await page.locator("body").inner_text(timeout=5000))[:1000]
            except Exception:
                pass
            status["search_body_hint"] = body_text
            status["search_looks_blocked"] = any(
                marker in body_text.lower()
                for marker in ["something went wrong", "notfound", "try again", "couldn't find"]
            )
        except PlaywrightTimeoutError as e:
            status["search_error"] = f"timeout: {e}"

        cookies = await context.cookies(["https://www.tiktok.com", "https://tiktok.com"])
        cookies = [normalize_cookie(c) for c in cookies]
        storage = await context.storage_state()

        out_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        storage_out.write_text(json.dumps(storage, ensure_ascii=False, indent=2), encoding="utf-8")
        await context.close()

    names = {c.get("name") for c in cookies}
    status.update(
        {
            "cookie_count": len(cookies),
            "has_sessionid": "sessionid" in names,
            "has_msToken": "msToken" in names,
            "cookies_out": str(out_path),
            "storage_out": str(storage_out),
        }
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
