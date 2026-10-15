#!/usr/bin/env bash
set -euo pipefail

export API_PORT="${API_PORT:-8000}"
export WEB_PORT="${PORT:-7860}"
export API_INTERNAL_URL="http://127.0.0.1:${API_PORT}"

echo "[AtlasRec Cloud] Starting FastAPI + ML Recommendation Engine on 127.0.0.1:${API_PORT}..."
HOST="127.0.0.1" PORT="${API_PORT}" python scripts/live_server.py &
API_PID=$!

echo "[AtlasRec Cloud] Waiting for API server readiness..."
for i in $(seq 1 120); do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${API_PORT}/healthz', timeout=2)" >/dev/null 2>&1; then
    echo "[AtlasRec Cloud] FastAPI engine is ready!"
    break
  fi
  sleep 2
done

echo "[AtlasRec Cloud] Starting Next.js Storefront on 0.0.0.0:${WEB_PORT}..."
exec npm run start --workspace apps/web -- --hostname 0.0.0.0 --port "${WEB_PORT}"
