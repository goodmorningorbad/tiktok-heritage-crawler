#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/root/workspace"
REPO_DIR="$BASE_DIR/TikTok-Api"
VENV_DIR="$BASE_DIR/tiktok-api-venv"
CRAWLER_DIR="$BASE_DIR/tiktok-heritage-crawler"

mkdir -p "$BASE_DIR" "$CRAWLER_DIR/data"

if [[ -d "$REPO_DIR/.git" ]]; then
  git -C "$REPO_DIR" pull --ff-only
else
  git clone --depth 1 https://github.com/davidteather/TikTok-Api.git "$REPO_DIR"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install -U pip setuptools wheel
"$VENV_DIR/bin/pip" install -e "$REPO_DIR"
"$VENV_DIR/bin/python" -m playwright install chromium --with-deps

cat > "$CRAWLER_DIR/.env.example" <<'ENV'
# 从 tiktok.com Cookie 获取
ms_token=""
TIKTOK_BROWSER=chromium
TIKTOK_TIMEOUT_MS=90000
# 单个 msToken 容易快速刷新；更稳的是导出整组 TikTok cookies JSON，然后填这个路径
# TIKTOK_COOKIES_JSON=/root/workspace/tiktok-heritage-crawler/cookies.json
# HTTPS_PROXY=http://user:pass@host:port
# HTTP_PROXY=http://user:pass@host:port
ENV

echo "OK: TikTok crawler environment deployed at $CRAWLER_DIR"
