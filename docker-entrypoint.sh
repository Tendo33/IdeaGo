#!/bin/sh
# docker-entrypoint.sh — inject runtime config into frontend at container startup

FRONTEND_DIST="/app/frontend/dist"
CONFIG_FILE="${FRONTEND_DIST}/env-config.js"

if [ -d "$FRONTEND_DIST" ]; then
  # Use printf to safely escape single quotes in the key value
  SAFE_KEY=$(printf '%s' "${APP_API_KEY:-}" | sed "s/'/\\\\'/g")
  printf "window.__APP_CONFIG__ = { apiKey: '%s' };\n" "$SAFE_KEY" > "$CONFIG_FILE"
fi

exec "$@"
