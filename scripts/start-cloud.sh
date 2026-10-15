#!/usr/bin/env bash
set -euo pipefail

export API_PORT="${API_PORT:-8000}"
export WEB_PORT="${PORT:-7860}"
export API_INTERNAL_URL="http://127.0.0.1:${API_PORT}"
export COOKIE_SECURE="${COOKIE_SECURE:-true}"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=160}"

echo "[AtlasRec Cloud] Launching FastAPI + ML Recommendation Engine on 127.0.0.1:${API_PORT} in background..."
HOST="127.0.0.1" PORT="${API_PORT}" python scripts/live_server.py &

echo "[AtlasRec Cloud] Starting Next.js Storefront immediately on 0.0.0.0:${WEB_PORT}..."
exec npm run start --workspace apps/web -- --hostname 0.0.0.0 --port "${WEB_PORT}"
