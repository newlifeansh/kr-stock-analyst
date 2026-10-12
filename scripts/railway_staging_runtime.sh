#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: railway_staging_runtime.sh up|prepare|down" >&2
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

application_runtime_state() {
  railway service list -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" --json |
    python3 -c '
import json, sys
service = next((row for row in json.load(sys.stdin) if row.get("id") == sys.argv[1]), None)
if service is None:
    raise SystemExit("Staging application service not found")
status = service.get("status")
running = int((service.get("replicas") or {}).get("running") or 0)
if running > 0 and status in ("SUCCESS", "SLEEPING") and not service.get("deploymentStopped"):
    print("running")
elif running == 0 and (status in ("FAILED", "CRASHED") or service.get("deploymentStopped")):
    print("stopped")
elif running == 0 and status in (None, "REMOVED", "SUCCESS", "SLEEPING"):
    print("idle")
else:
    print("transitional")
' "$1"
}

wait_for_application() {
  local service="$1" expected="$2"
  local deadline=$((SECONDS + RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS)) state
  while ((SECONDS < deadline)); do
    state="$(application_runtime_state "$service")" || return 1
    if [[ "$expected" == "running" && "$state" == "running" ]] ||
       [[ "$expected" == "stopped" && ("$state" == "stopped" || "$state" == "idle") ]]; then
      return 0
    fi
    sleep 5
  done
  echo "Staging application $service did not reach $expected" >&2
  return 1
}

resume_application() {
  local service="$1" state
  state="$(application_runtime_state "$service")" || return 1
  if [[ "$state" == "stopped" ]]; then
    echo "Restarting stopped staging deployment without rebuilding: $service" >&2
    railway restart -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" \
      --service "$service" --yes --json >/dev/null || return 1
  fi
  wait_for_application "$service" running
}

stop_application() {
  local service="$1" state
  state="$(application_runtime_state "$service")" || return 1
  if [[ "$state" != "stopped" && "$state" != "idle" ]]; then
    # Railway scale updates desired configuration but may leave the active
    # deployment serving. Stop that deployment explicitly, retaining its
    # service, source image and any volume, before shutting down the DB.
    railway down -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" \
      --service "$service" --yes || return 1
  fi
  wait_for_application "$service" stopped
}

wait_until_ready() {
  local deadline=$((SECONDS + RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS))
  while ((SECONDS < deadline)); do
    # /readyz executes SELECT 1: a scaled replica alone does not prove DB readiness.
    if curl -fsS --max-time 10 "${QA_BASE_URL%/}/readyz" 2>/dev/null |
      python3 -c 'import json,sys; p=json.load(sys.stdin); sys.exit(0 if p.get("status")=="ok" and p.get("database_ok") is True else 1)' 2>/dev/null; then
      return 0
    fi
    sleep 5
  done
  echo "Domestic staging failed its database-backed readiness check" >&2
  return 1
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
  # Do not remove the DB while web/collector processes are still shutting down.
  stop_application "$RAILWAY_WEB_SERVICE" || status=1
  stop_application "$RAILWAY_COLLECTOR_SERVICE" || status=1
  if [[ "$status" -ne 0 ]]; then
    echo "Keeping staging DB running because application shutdown is unverified" >&2
    return "$status"
  fi
  stop_database || status=1
  return "$status"
}

rollback_after_failed_start() {
  echo "Domestic staging start failed; scaling every staging service back to zero" >&2
  power_down || true
  exit 1
}

if [[ $# -ne 1 || ("$1" != "up" && "$1" != "prepare" && "$1" != "down") ]]; then
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
RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS="${RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS:-180}"
validate_selector RAILWAY_ENVIRONMENT
if [[ ! "$RAILWAY_DATABASE_WARMUP_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "RAILWAY_DATABASE_WARMUP_SECONDS must be a non-negative integer" >&2
  exit 2
fi
if [[ ! "$RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS" =~ ^[0-9]+$ || "$RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS" -eq 0 ]]; then
  echo "RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if [[ ! "$RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS" =~ ^[0-9]+$ || "$RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS" -eq 0 ]]; then
  echo "RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if [[ "$1" == "up" ]]; then
  require_value QA_BASE_URL
  [[ "$QA_BASE_URL" =~ ^https?:// ]] || exit 2
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
if [[ "$1" == "up" ]]; then
  resume_application "$RAILWAY_COLLECTOR_SERVICE" || rollback_after_failed_start
  resume_application "$RAILWAY_WEB_SERVICE" || rollback_after_failed_start
  wait_until_ready || rollback_after_failed_start
fi
