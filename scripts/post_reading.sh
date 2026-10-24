#!/usr/bin/env bash
# Smoke-test the ingest endpoint (what the ESP32 does).
#   export CONVEX_SITE_URL=https://<deployment>.convex.site   # .site, not .cloud
#   export INGEST_TOKEN=...
#   scripts/post_reading.sh [value] [raw]
set -euo pipefail
: "${CONVEX_SITE_URL:?set CONVEX_SITE_URL (https://<name>.convex.site)}"
: "${INGEST_TOKEN:?set INGEST_TOKEN}"

echo "health:"; curl -sS "$CONVEX_SITE_URL/health"; echo
echo "reading:"
curl -sS -X POST "$CONVEX_SITE_URL/ingest/reading" \
  -H "Content-Type: application/json" \
  -H "X-Dowser-Token: $INGEST_TOKEN" \
  -d "{\"deviceId\":\"esp32-test\",\"value\":${1:-12},\"raw\":${2:-512},\"isReplay\":true,\"timestamp\":$(($(date +%s) * 1000))}"
echo
echo "bad token (expect 401):"
curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$CONVEX_SITE_URL/ingest/reading" \
  -H "X-Dowser-Token: wrong" -d '{}'
