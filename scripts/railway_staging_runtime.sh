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

railway_service_list() {
  local payload attempt=0 delay
  while ((attempt < 4)); do
    if payload="$(railway service list -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" --json 2>&1)"; then
      printf '%s' "$payload"
      return 0
    fi
    if [[ "$payload" =~ Try\ again\ in\ ([0-9]+)\ seconds && "$attempt" -lt 3 ]]; then
      delay="${BASH_REMATCH[1]}"
      if ((delay > 60)); then delay=60; fi
      if ((delay < 1)); then delay=1; fi
      echo "Staging status query rate limited; retrying after ${delay}s" >&2
      sleep "$delay"
      attempt=$((attempt + 1))
    else
      echo "Railway service status query failed; state remains unverified" >&2
      return 1
    fi
  done
  return 1
}

scale_service() {
  local role="$1"
  local service="$2"
  local replicas="$3"

  local payload assignments result
  local -a targets=()
  payload="$(railway_service_list)" || return 1
  assignments="$(printf '%s' "$payload" | python3 -c '
import json, re, sys
rows = json.load(sys.stdin)
service = next((row for row in rows if row.get("id") == sys.argv[1]), None)
if service is None:
    raise SystemExit("Staging scale target was not found")
regions = service.get("regions")
if not isinstance(regions, list):
    raise SystemExit("Staging region evidence is missing")
names = [row.get("name") for row in regions]
if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name) for name in names) or len(names) != len(set(names)):
    raise SystemExit("Invalid staging region evidence")
target = sys.argv[2]
# Railway scale merges with the latest deployment manifest. A friendly alias
# can add a second region while leaving a legacy sfo replica intact. Require
# the observed canonical ID and explicitly clear every other selected-app region.
if names and target not in names:
    raise SystemExit("Use the observed canonical Railway region ID, not an alias")
for name in sorted(set(names) | {target}):
    print(f"{name}={sys.argv[3] if name == target else 0}")
' "$service" "$RAILWAY_REGION" "$replicas")" || return 1
  while IFS= read -r assignment; do targets+=("$assignment"); done <<< "$assignments"
  echo "Scaling domestic staging $role to $replicas replica(s) across all observed regions" >&2
  result="$(railway scale \
    -p "$RAILWAY_PROJECT_ID" \
    --environment "$RAILWAY_ENVIRONMENT" \
    --service "$service" \
    "${targets[@]}" \
    --json)" || return 1
  printf '%s' "$result" | python3 -c '
import json, sys
regions = json.load(sys.stdin).get("regions")
if not isinstance(regions, dict):
    raise SystemExit("Railway did not acknowledge the region scale patch")
counts = {name: (value or {}).get("numReplicas", 0) for name, value in regions.items()}
if any(type(count) is not int or count < 0 for count in counts.values()):
    raise SystemExit("Invalid region scale acknowledgement")
target, desired = sys.argv[1], int(sys.argv[2])
if counts.get(target, 0) != desired or any(count for name, count in counts.items() if name != target):
    raise SystemExit("Railway scale acknowledgement retains an unexpected replica")
' "$RAILWAY_REGION" "$replicas"
}

database_runtime_state() {
  local payload

  payload="$(railway_service_list)" || return 1

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
  local payload
  payload="$(railway_service_list)" || return 1
  printf '%s' "$payload" | python3 -c '
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
    sleep "$RAILWAY_STATE_POLL_SECONDS"
  done
  echo "Staging application $service did not reach $expected" >&2
  return 1
}

resume_application() {
  local service="$1" state
  state="$(application_runtime_state "$service")" || return 1
  if [[ "$state" == "stopped" ]]; then
    echo "Restarting stopped staging deployment without rebuilding: $service" >&2
    if ! railway restart -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" \
      --service "$service" --yes --json >/dev/null; then
      redeploy_pinned_application "$service" || return 1
    fi
  elif [[ "$state" == "idle" ]]; then
    redeploy_pinned_application "$service" || return 1
  fi
  wait_for_application "$service" running
}

redeploy_pinned_application() {
  local service="$1" payload
  # Removed deployments cannot restart, and connecting the same source image
  # may be a no-op. Pull the configured source only after its exact immutable
  # identity has been checked. Never rebuild a repo or follow a mutable tag.
  require_value RAILWAY_RESUME_IMAGE_REF || return 1
  payload="$(railway_service_list)" || return 1
  printf '%s' "$payload" | python3 -c '
import json, sys
rows = json.load(sys.stdin)
service = next((row for row in rows if row.get("id") == sys.argv[1]), {})
source = service.get("source") or {}
if source.get("repo") or source.get("image") != sys.argv[2]:
    raise SystemExit("Refusing restart fallback: configured image does not match the pinned candidate")
' "$service" "$RAILWAY_RESUME_IMAGE_REF" || return 1
  echo "Restoring removed staging deployment from its verified immutable image: $service" >&2
  railway redeploy -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" \
    --service "$service" --from-source --yes --json >/dev/null || return 1
}

stop_application() {
  local service="$1" state attempts=0 quiet_since=-1
  local deadline=$((SECONDS + RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS))
  while ((SECONDS < deadline)); do
    state="$(application_runtime_state "$service")" || return 1
    if [[ "$state" == "stopped" || "$state" == "idle" ]]; then
      if ((quiet_since < 0)); then quiet_since=$SECONDS; fi
      if ((SECONDS - quiet_since >= RAILWAY_APPLICATION_QUIET_SECONDS)); then return 0; fi
    else
      quiet_since=-1
      # A scale patch can queue a new deployment after the previous one stops.
      # Stop only active deployments of this explicitly selected staging app,
      # bounded to three attempts, then require a stable zero-process window.
      if [[ "$state" == "running" && "$attempts" -lt 3 ]]; then
        railway down -p "$RAILWAY_PROJECT_ID" --environment "$RAILWAY_ENVIRONMENT" \
          --service "$service" --yes || return 1
        attempts=$((attempts + 1))
        continue
      fi
    fi
    sleep "$RAILWAY_STATE_POLL_SECONDS"
  done
  echo "Staging application $service did not remain stopped" >&2
  return 1
}

wait_until_ready() {
  local deadline=$((SECONDS + RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS))
  while ((SECONDS < deadline)); do
    # /readyz executes SELECT 1: a scaled replica alone does not prove DB readiness.
    if curl -fsS --max-time 10 "${QA_BASE_URL%/}/readyz" 2>/dev/null |
      python3 -c 'import json,sys; p=json.load(sys.stdin); sys.exit(0 if p.get("status")=="ok" and p.get("database_ok") is True else 1)' 2>/dev/null; then
      return 0
    fi
    sleep "$RAILWAY_STATE_POLL_SECONDS"
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
    sleep "$RAILWAY_STATE_POLL_SECONDS"
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
    sleep "$RAILWAY_STATE_POLL_SECONDS"
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
    sleep "$RAILWAY_STATE_POLL_SECONDS"
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
# Same-image restore took 198s before the container started (run 38309633357).
# Allow bounded provisioning time plus Railway's configured 300s health window.
RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS="${RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS:-600}"
RAILWAY_APPLICATION_QUIET_SECONDS="${RAILWAY_APPLICATION_QUIET_SECONDS:-30}"
RAILWAY_STATE_POLL_SECONDS="${RAILWAY_STATE_POLL_SECONDS:-15}"
validate_selector RAILWAY_ENVIRONMENT
if [[ "$RAILWAY_ENVIRONMENT" != "staging" ]]; then
  echo "This runtime controller only operates on the staging environment" >&2
  exit 2
fi
if [[ -n "${RAILWAY_RESUME_IMAGE_REF:-}" ]]; then
  if [[ "$RAILWAY_ENVIRONMENT" != "staging" || ! "$RAILWAY_RESUME_IMAGE_REF" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]]; then
    echo "Resume fallback requires a staging environment and an exact GHCR sha256 image" >&2
    exit 2
  fi
fi
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
if [[ ! "$RAILWAY_APPLICATION_QUIET_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "RAILWAY_APPLICATION_QUIET_SECONDS must be a non-negative integer" >&2
  exit 2
fi
if [[ ! "$RAILWAY_STATE_POLL_SECONDS" =~ ^[0-9]+$ || "$RAILWAY_STATE_POLL_SECONDS" -lt 1 || "$RAILWAY_STATE_POLL_SECONDS" -gt 60 ]]; then
  echo "RAILWAY_STATE_POLL_SECONDS must be between 1 and 60" >&2
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
