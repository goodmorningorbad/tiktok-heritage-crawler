#!/usr/bin/env bash
set -euo pipefail

WORKDIR="/root/workspace/tiktok-heritage-crawler"
VENV="/root/workspace/tiktok-api-venv/bin/activate"
LOG_DIR="$WORKDIR/data/vps_cookie_refresh_logs"
mkdir -p "$LOG_DIR"

cd "$WORKDIR"
source "$VENV"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

shopt -s nullglob
cookie_files=(cookies/*.json)
accounts=()
for f in "${cookie_files[@]}"; do
  base="$(basename "$f" .json)"
  [[ "$base" == *_storage ]] && continue
  [[ "$base" == *_vps_test ]] && continue
  [[ "$base" == cookie* ]] && continue
  accounts+=("$base")
done

if [[ ${#accounts[@]} -eq 0 ]]; then
  echo "[$(date -Is)] No account cookie files found under $WORKDIR/cookies" >&2
  exit 1
fi

status=0
for account in "${accounts[@]}"; do
  echo "[$(date -Is)] === VPS refreshing $account ==="
  python refresh_tiktok_cookies.py \
    --profile-dir "profiles_vps/$account" \
    --cookies-in "cookies/$account.json" \
    --out "cookies/$account.json" \
    --storage-out "cookies/${account}_storage.json" \
    --query "chinesenewyear" \
    --headless \
    --timeout-ms "${TIKTOK_TIMEOUT_MS:-90000}" \
    > "$LOG_DIR/${account}.latest.json" || status=$?

  if [[ $status -ne 0 ]]; then
    echo "[$(date -Is)] Refresh failed for $account with exit $status" >&2
    break
  fi

  python3 - "$account" <<'PY'
import json, pathlib, sys
account = sys.argv[1]
p = pathlib.Path('cookies') / f'{account}.json'
data = json.loads(p.read_text(encoding='utf-8'))
names = {c.get('name') for c in data if isinstance(c, dict)}
print(f"[{account}] cookie_count={len(data)} has_sessionid={'sessionid' in names} has_msToken={'msToken' in names}")
if 'sessionid' not in names or 'msToken' not in names:
    raise SystemExit(2)
PY
done

echo "[$(date -Is)] VPS cookie refresh complete for ${#accounts[@]} account(s): ${accounts[*]}"
