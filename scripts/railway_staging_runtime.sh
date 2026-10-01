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
    -p "$RAILWAY_PROJECT_ID" \
    --environment "$RAILWAY_ENVIRONMENT" \
    --service "$service" \
    "${RAILWAY_REGION}=${replicas}" \
    "sfo=0" \
    --json >/dev/null
}

database_runtime_state() {
  local payload

  payload="$({
    railway service list \
      -p "$RAILWAY_PROJECT_ID" \
      --environment "$RAILWAY_ENVIRONMENT" \
      --json
  })" || return 1

  printf '%s' "$payload" | python3 -c '
import json
import sys

service_id = sys.argv[1]
try:
    services = json.load(sys.stdin)
except (json.JSONDecodeError, TypeError):
    raise SystemExit("Railway returned invalid service status JSON")

service = next((item for item in services if item.get("id") == service_id), None)
if service is None:
    raise SystemExit("Railway database service was not found in the environment")

status = service.get("status")
stopped = bool(service.get("deploymentStopped"))
replicas = service.get("replicas") or {}
running_replicas = replicas.get("running", 0)

if stopped or status in (None, "REMOVED"):
    print("inactive")
elif status in ("FAILED", "CRASHED") and running_replicas == 0:
    print("inactive")
elif status in ("SUCCESS", "SLEEPING"):
    print("running")
elif status in ("BUILDING", "DEPLOYING", "INITIALIZING", "QUEUED", "WAITING", "REMOVING"):
    print("transitional")
else:
    raise SystemExit(f"Unexpected Railway database deployment status: {status!r}")
' "$RAILWAY_DATABASE_SERVICE"
}

wait_for_database_running() {
  local deadline=$((SECONDS + RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS))
  local state

  while ((SECONDS < deadline)); do
    state="$(database_runtime_state)" || return 1
    if [[ "$state" == "running" ]]; then
      echo "Domestic staging database is running" >&2
      return 0
    fi
    sleep 5
  done
  echo "Domestic staging database did not start within ${RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS}s" >&2
  return 1
}

start_database() {
  local state

  state="$(database_runtime_state)" || return 1
  if [[ "$state" == "running" ]]; then
    echo "Domestic staging database is already running" >&2
    return 0
  fi

  if [[ "$state" == "inactive" ]]; then
    echo "Starting domestic staging database from its configured source image" >&2
    railway redeploy \
      -p "$RAILWAY_PROJECT_ID" \
      --environment "$RAILWAY_ENVIRONMENT" \
      --service "$RAILWAY_DATABASE_SERVICE" \
      --from-source \
      --yes \
      --json >/dev/null || return 1
  fi

  wait_for_database_running
}

stop_database() {
  local deadline=$((SECONDS + RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS))
  local state

  state="$(database_runtime_state)" || return 1
  while [[ "$state" == "transitional" && SECONDS -lt deadline ]]; do
    sleep 5
    state="$(database_runtime_state)" || return 1
  done

  if [[ "$state" == "inactive" ]]; then
    echo "Domestic staging database is already stopped" >&2
    return 0
  fi
  if [[ "$state" != "running" ]]; then
    echo "Domestic staging database did not reach a removable state" >&2
    return 1
  fi

  echo "Stopping domestic staging database deployment while preserving its service and volume" >&2
  railway down \
    -p "$RAILWAY_PROJECT_ID" \
    --environment "$RAILWAY_ENVIRONMENT" \
    --service "$RAILWAY_DATABASE_SERVICE" \
    --yes || return 1

  while ((SECONDS < deadline)); do
    state="$(database_runtime_state)" || return 1
    if [[ "$state" == "inactive" ]]; then
      echo "Domestic staging database is stopped" >&2
      return 0
    fi
    sleep 5
  done
  echo "Domestic staging database did not stop within ${RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS}s" >&2
  return 1
}

power_down() {
  local status=0

  scale_service web "$RAILWAY_WEB_SERVICE" 0 || status=1
  scale_service collector "$RAILWAY_COLLECTOR_SERVICE" 0 || status=1
  stop_database || status=1
  return "$status"
}

rollback_after_failed_start() {
  echo "Domestic staging start failed; scaling every staging service back to zero" >&2
  power_down || true
  exit 1
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
RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS="${RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS:-300}"
validate_selector RAILWAY_ENVIRONMENT
if [[ ! "$RAILWAY_DATABASE_WARMUP_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "RAILWAY_DATABASE_WARMUP_SECONDS must be a non-negative integer" >&2
  exit 2
fi
if [[ ! "$RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS" =~ ^[0-9]+$ || "$RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS" -eq 0 ]]; then
  echo "RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi

if [[ "$1" == "down" ]]; then
  power_down
  exit $?
fi

start_database || rollback_after_failed_start
if [[ "$RAILWAY_DATABASE_WARMUP_SECONDS" -gt 0 ]]; then
  sleep "$RAILWAY_DATABASE_WARMUP_SECONDS"
fi
scale_service collector "$RAILWAY_COLLECTOR_SERVICE" 1 || rollback_after_failed_start
scale_service web "$RAILWAY_WEB_SERVICE" 1 || rollback_after_failed_start
