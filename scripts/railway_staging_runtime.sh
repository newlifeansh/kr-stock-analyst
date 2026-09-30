#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: railway_staging_runtime.sh up|down" >&2
}

require_value() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    return 1
  fi
}

validate_selector() {
  local name="$1"
  local value="${!name}"
  if [[ ! "$value" =~ ^[0-9A-Za-z._-]+$ ]]; then
    echo "Invalid Railway selector in $name" >&2
    return 1
  fi
}

scale_service() {
  local role="$1"
  local service="$2"
  local replicas="$3"

  echo "Scaling domestic staging $role to $replicas replica(s)" >&2
  railway scale \
    --project "$RAILWAY_PROJECT_ID" \
    --environment "$RAILWAY_ENVIRONMENT" \
    --service "$service" \
    "${RAILWAY_REGION}=${replicas}" \
    --json >/dev/null
}

power_down() {
  local status=0

  scale_service web "$RAILWAY_WEB_SERVICE" 0 || status=1
  scale_service collector "$RAILWAY_COLLECTOR_SERVICE" 0 || status=1
  scale_service database "$RAILWAY_DATABASE_SERVICE" 0 || status=1
  return "$status"
}

rollback_after_failed_start() {
  echo "Domestic staging start failed; scaling every staging service back to zero" >&2
  power_down || true
  exit 1
}

wait_until_ready() {
  local base_url="${RAILWAY_READY_URL:-}"
  local timeout_seconds="${RAILWAY_READY_TIMEOUT_SECONDS:-300}"
  local deadline

  if [[ -z "$base_url" ]]; then
    return 0
  fi
  if [[ ! "$base_url" =~ ^https://[^[:space:]]+$ ]]; then
    echo "RAILWAY_READY_URL must be an https URL" >&2
    return 1
  fi
  if [[ ! "$timeout_seconds" =~ ^[0-9]+$ || "$timeout_seconds" -eq 0 ]]; then
    echo "RAILWAY_READY_TIMEOUT_SECONDS must be a positive integer" >&2
    return 1
  fi

  deadline=$((SECONDS + timeout_seconds))
  while ((SECONDS < deadline)); do
    if curl --fail --silent --show-error --max-time 10 \
      "${base_url%/}/healthz" >/dev/null 2>&1; then
      echo "Domestic staging health check passed" >&2
      return 0
    fi
    sleep 5
  done
  echo "Domestic staging did not become healthy within ${timeout_seconds}s" >&2
  return 1
}

if [[ $# -ne 1 || ("$1" != "up" && "$1" != "down") ]]; then
  usage
  exit 2
fi

for variable in \
  RAILWAY_PROJECT_ID \
  RAILWAY_WEB_SERVICE \
  RAILWAY_COLLECTOR_SERVICE \
  RAILWAY_DATABASE_SERVICE \
  RAILWAY_REGION; do
  require_value "$variable"
  validate_selector "$variable"
done

RAILWAY_ENVIRONMENT="${RAILWAY_ENVIRONMENT:-staging}"
RAILWAY_DATABASE_WARMUP_SECONDS="${RAILWAY_DATABASE_WARMUP_SECONDS:-20}"
validate_selector RAILWAY_ENVIRONMENT
if [[ ! "$RAILWAY_DATABASE_WARMUP_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "RAILWAY_DATABASE_WARMUP_SECONDS must be a non-negative integer" >&2
  exit 2
fi

if [[ "$1" == "down" ]]; then
  power_down
  exit $?
fi

scale_service database "$RAILWAY_DATABASE_SERVICE" 1 || rollback_after_failed_start
if [[ "$RAILWAY_DATABASE_WARMUP_SECONDS" -gt 0 ]]; then
  sleep "$RAILWAY_DATABASE_WARMUP_SECONDS"
fi
scale_service collector "$RAILWAY_COLLECTOR_SERVICE" 1 || rollback_after_failed_start
scale_service web "$RAILWAY_WEB_SERVICE" 1 || rollback_after_failed_start
wait_until_ready || rollback_after_failed_start
