# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A data-journalism research toolkit that measures how China's 44 UNESCO Intangible
Cultural Heritage (ICH) items spread overseas on **TikTok** (primary) and **YouTube**
(reference platform). It is not a generic scraper — it is an instrument built around a
research hypothesis (that hard-to-"functionalize" / niche / endangered heritage items
are nearly invisible abroad), and almost every design decision exists to *verify or
falsify* that hypothesis without contaminating the evidence.

**Read `docs/数据采集规格说明1.1.md` before doing any substantive work.** It is the
governing spec. The crawler/analysis code only makes sense in light of its methodology
red lines (below).

## Non-negotiable methodology red lines

These are enforced in code and must never be "helpfully" violated. Agents break these by
trying to make data look clean:

1. **Never delete raw data.** Cleaning/labeling steps produce *annotated copies*; raw
   captures stay untouched. `derive_*.py` / `apply_*.py` read immutable baselines and
   write only to `data/derived/`.
2. **`negative_terms` label, never exclude.** Noise (e.g. Mexican papercut, hand-shadow
   puppetry) is collected and stored, only *marked* `low_relevance`. The noise ratio is
   itself evidence for the "diluted recognizability" hypothesis — discarding it destroys
   the evidence.
3. **Never auto-reclassify content type or auto-expand keywords to chase recall.** Forcing
   recall manufactures reach that does not exist and erases the phenomenon under study.
4. **Zero results are a finding.** Record `total_results=0` / `result_class=zero_real`
   faithfully; do not skip empty terms.
5. **`failed` ≠ `zero_real` ≠ `has_data` — keep strictly separate.** `failed` = rate-limit
   / technical noise (must be re-collected, never counted as low-reach). `zero_real` = the
   term genuinely returned nothing. Downstream "nearly invisible" conclusions may only use
   `zero_real`, never `failed`. This three-way split lives in `crawler.py` and is preserved
   through every stage.
6. **Missing values stay blank, never guessed** (e.g. `author_region` / `author_language`).
7. **Only China's items count.** Mongolia's khoomei, Japanese calligraphy, Mexican papercut
   etc. are `irrelevant`; ambiguous nationality is `uncertain`, never guessed. See the
   adjudication rules in §5.2 of the spec.

Roles (spec §9): **humans** make all relevance/"is this real low-reach" judgments;
agents only assist (export sampling lists, write clean scripts). Do not have an agent make
research judgment calls.

## Environment & paths (important)

The committed code targets a **VPS at `/root/workspace/`**, not this Windows checkout.
Hardcoded paths you will see and must account for:

- `batch_collect.py`: `WORKDIR = /root/workspace/tiktok-heritage-crawler`
- `pool_scheduler.py`: `DEFAULT_PYTHON = /root/workspace/tiktok-api-venv/bin/python3`
- Cookies under `cookies/acc{1..4}.json`; SOCKS proxies on `127.0.0.1:1092-1094`

The actual collection runtime runs on that VPS (proxy pool, account rotation, long-running
crawls). This local repo is mainly for editing scripts and running the **derived/analysis**
steps, which read committed/sample data. When running collection code locally you must
adjust paths and provide your own cookies + proxies.

`.env` (copy from `.env.example`) supplies `ms_token` and TikTok session config. `data/`,
`cookies/`, `*.ndjson`, `*.log`, `.env` are gitignored — collected datasets are not committed
except the frozen `data/final/` package.

## Commands

Setup (VPS): `bash deploy.sh` — clones davidteather/TikTok-Api, builds venv, installs
Playwright chromium.

```bash
# --- Collection (crawler.py): three channels ---
python crawler.py search   --keywords "太极,taichi" --count 50 --out data/search.ndjson
python crawler.py hashtag  --hashtags "hanfu,papercutting" --count 50 --out data/hashtags.ndjson
python crawler.py hashtag-stats --hashtags "hanfu" --out data/hashtag_stats.ndjson  # challenge scale only

# --- Batch over all 44 projects from keyword config ---
python batch_collect.py --channels both --videos-per-term 20 --limit-projects 3   # smoke test
# channels: search | hashtag | hashtag-stats | both ; reads config/unesco_ich_keywords.v1.json

# --- Production search collection: account-rotation + cooldown scheduler (preferred over pool_runner) ---
python pool_scheduler.py --count 2000 --phase search_baseline           # resumable; --run-id <id> to continue
python pool_runner.py --dry-run --channels both --videos-per-term 2000   # static account×IP assignment (legacy)

# --- Labeling & export ---
python quality_label.py data/<combined>.csv          # adds 3-tier relevance labels (likely/needs_review/low)
python ndjson_to_csv.py data/search.ndjson data/search.csv

# --- Config tooling ---
python scripts/validate_keyword_config.py            # validate config/unesco_ich_keywords.v1.json
python scripts/build_keyword_config.py

# --- YouTube reference channel (needs YOUTUBE_API_KEY / GOOGLE_API_KEY) ---
python scripts/collect_youtube_search.py
```

There is **no test suite, linter, or build step.** `verify_ceiling_*.py`, `probe_*.py`,
`run_*test*.py` are one-off empirical probes against the live TikTok API (documenting
pagination-ceiling behavior), not unit tests.

## Architecture

### Collection layer
- **`crawler.py`** — the single low-level collector (`TikTokApi` + Playwright cookies).
  Subcommands: `search`, `hashtag`, `hashtag-stats`. The hard part is `collect_search_pagewise`:
  TikTok's `/api/search/item/full/` requires carrying `search_id` (from page-1 `log_pb.impr_id`)
  + `from_page` + `web_search_code` to paginate past page 1. It classifies each term's outcome
  into `depth_verdict` (`ceiling_capped` / `exhausted` / `rate_limited` / `count_reached`) and
  `result_class` (`failed` / `zero_real` / `has_data`) using a **has_more transition pattern**,
  not cursor numbers (cursor proved unreliable — see the long inline comments). Emits
  `SEARCH_META` lines on stderr that upstream parses. Every row carries `collector_meta()`
  provenance (account, proxy region/IP/ISP) so any datapoint traces back to who/where collected it.
- **`batch_collect.py`** — drives `crawler.py` per project across all terms in the keyword
  config, enriches rows with `heritage_*` fields, dedups by video id (keeping `matched_sources`),
  writes combined NDJSON+CSV + a `collection_report_*.json`. Inter-term/inter-project cooldowns
  fight rate limiting.
- **`pool_scheduler.py`** (preferred) vs **`pool_runner.py`** (legacy): both pin
  `(account, cookie, proxy, region)` for single-region-baseline + traceability. Runner statically
  assigns whole projects to slots (one rate-limited account kills its whole batch). Scheduler uses
  finest-grain `(project, term)` work units in a queue with account rotation + cooldown, so a
  rate-limit costs one term (which re-queues, up to `MAX_TERM_RETRIES`, then becomes
  `unresolved_failed` — never `zero_real`). It is resumable via `--run-id`. See `docs/POOL_RUNNER.md`
  for the US residential proxy pool topology.
- **`refresh_tiktok_cookies.py`** + `vps_refresh_all_cookies.sh` — Playwright persistent-profile
  cookie refresh (a systemd timer runs this every 30min on the VPS).

### Labeling layer
- **`quality_label.py`** — conservative, additive 3-tier relevance scoring
  (`likely_relevant` / `needs_review` / `low_relevance`). Reads per-project term groups from
  the keyword config (`core_terms` / `search_terms` / `negative_terms` / `hashtag_terms`), scores
  on term hits, China-context, CJK, negative hits, etc. Adds columns; deletes nothing.

### Derivation / analysis layer (`scripts/derive_*.py`, `scripts/apply_*.py`)
These read the **frozen baseline** (`data/sched_run_20260612_030425/`) and config, and write only
to `data/derived/`. They compute project-level reach, relevance-aware reach, stock×reach matrices /
quadrants, deep-crawl candidates, YouTube reach, and apply manual-review corrections and audit
demotions (e.g. `apply_tiktok_china_signal_filter.py`, `apply_tiktok_final_audit_display_corrections.py`,
`apply_manual_review_to_matrix.py`). `build_tiktok_visual_dashboard.py` renders the dashboard. AI-audit
helpers (`run_softr_ai_audit_exam.py`, `score_ai_audit.py`, prompts under `_incoming_ai_audit_files/`)
calibrate/validate machine relevance against human labels.

### Config
- **`config/unesco_ich_keywords.v1.json`** — source of truth for the 44 ICH projects: each has
  `id`, `name_cn`/`name_en`, `category`, and the three keyword layers. `quality_label.py` and
  `batch_collect.py` both load it; a legacy `PROJECT_EXTRA_TERMS` dict in `quality_label.py` is the
  fallback when the file is absent.
- `config/youtube_ich_search_terms.v1.json`, `config/us_pool.json` (account×proxy pool).

### Outputs
- `data/sched_run_*/` — raw collection runs (`videos.ndjson`, `term_results.ndjson`,
  resumable `scheduler_state.json`). The `20260612_030425` run is the **fixed baseline** all
  analysis reads from.
- `data/derived/` — all computed analysis artifacts.
- `data/final/tiktok_closed_20260619/` — the **frozen, human-reviewed final TikTok deliverable**
  (project findings table, stock×reach matrix, row-level relevance labels). Read its `README.md`
  for column semantics. This is the report-ready package.

## Docs map (`docs/`, mostly Chinese)
- `数据采集规格说明1.1.md` — governing spec (read first). `数据采集规格说明.md` is the older 1.0.
- `POOL_RUNNER.md` — proxy pool & runner architecture.
- `HANDOFF.md` (repo root) + `docs/交接日志_*.md` / `采集交接记录_*.md` — chronological handoff logs;
  the latest dated one reflects current project state.
- `docs/review/` — human relevance-review adjudications and conflict resolutions (the v1 ruling).
- `docs/YouTube_*.md`, `docs/触达维*.md`, `docs/标签规模分层_*.md` — analysis writeups per stage.
