#!/usr/bin/env bash
# Smoke-test the ingest endpoint (what the ESP32 will do).
#   export CONVEX_SITE_URL=https://<deployment>.convex.site   # note: .site, not .cloud
#   export INGEST_TOKEN=...
#   scripts/post_reading.sh [raw] [corrected] [wellId]
set -euo pipefail
: "${CONVEX_SITE_URL:?set CONVEX_SITE_URL (https://<name>.convex.site)}"
: "${INGEST_TOKEN:?set INGEST_TOKEN}"

echo "health:"; curl -sS "$CONVEX_SITE_URL/health"; echo
echo "reading:"
curl -sS -X POST "$CONVEX_SITE_URL/ingest/reading" \
  -H "Content-Type: application/json" \
  -H "X-Dowser-Token: $INGEST_TOKEN" \
  -d "{\"deviceId\":\"esp32-test\",\"raw\":${1:-512},\"corrected\":${2:-12},\"wellId\":\"${3:-cand-001}\",\"isReplay\":true,\"ts\":$(($(date +%s) * 1000))}"
echo
echo "bad token (expect 401):"
curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$CONVEX_SITE_URL/ingest/reading" \
  -H "X-Dowser-Token: wrong" -d '{}'
