#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CLI=(npx -y @railway/cli)
PROJECT_NAME="${PROJECT_NAME:-kr-stock-analyst}"
APP_SERVICE="${APP_SERVICE:-insight-mcp}"
SOURCE_ENV="${SOURCE_ENV:-.env}"
GENERATED_ENV_FILE="${GENERATED_ENV_FILE:-.railway.generated.env}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
SKIP_DOMAIN="${SKIP_DOMAIN:-0}"
SKIP_VERIFY="${SKIP_VERIFY:-0}"

if [[ -x "$ROOT_DIR/.venv311/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv311/bin/python"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

log() {
  printf '\n[%s] %s\n' "railway-bootstrap" "$*"
}

extract_match_from_json() {
  local pattern="$1"
  "$PYTHON_BIN" - "$pattern" <<'PY'
import json
import re
import sys

pattern = re.compile(sys.argv[1])
payload = json.load(sys.stdin)

def walk(value):
    if isinstance(value, str) and pattern.search(value):
        print(value)
        raise SystemExit(0)
    if isinstance(value, dict):
        for item in value.values():
            walk(item)
    elif isinstance(value, list):
        for item in value:
            walk(item)

walk(payload)
raise SystemExit(1)
PY
}

json_has_service_name() {
  local service_name="$1"
  "$PYTHON_BIN" - "$service_name" <<'PY'
import json
import sys

target = sys.argv[1].strip().lower()
payload = json.load(sys.stdin)

items = payload if isinstance(payload, list) else [payload]
for item in items:
    name = str(item.get("name") or item.get("serviceName") or item.get("service", "")).strip().lower()
    if name == target:
        raise SystemExit(0)

raise SystemExit(1)
PY
}

require_login() {
  log "Checking Railway login"
  "${CLI[@]}" whoami >/dev/null
}

ensure_project_linked() {
  if [[ -d "$ROOT_DIR/.railway" ]]; then
    log "Railway project already linked"
    return
  fi
  log "Creating and linking Railway project: $PROJECT_NAME"
  "${CLI[@]}" init -n "$PROJECT_NAME" --json >/dev/null
}

ensure_app_service() {
  local services_json
  services_json="$("${CLI[@]}" service list --json)"
  if printf '%s' "$services_json" | json_has_service_name "$APP_SERVICE"; then
    log "App service already exists: $APP_SERVICE"
  else
    log "Creating app service: $APP_SERVICE"
    "${CLI[@]}" add --service "$APP_SERVICE" --json >/dev/null
  fi
  log "Linking current directory to app service: $APP_SERVICE"
  "${CLI[@]}" service link "$APP_SERVICE" >/dev/null
}

ensure_postgres_service() {
  local services_json
  services_json="$("${CLI[@]}" service list --json)"
  if printf '%s' "$services_json" | "$PYTHON_BIN" - <<'PY'
import json
import sys

payload = json.load(sys.stdin)
items = payload if isinstance(payload, list) else [payload]
for item in items:
    name = str(item.get("name") or item.get("serviceName") or "").strip().lower()
    if "postgres" in name:
        raise SystemExit(0)
raise SystemExit(1)
PY
  then
    log "Postgres service already exists"
  else
    log "Adding Postgres service"
    "${CLI[@]}" add --database postgres --json >/dev/null
  fi
  log "Re-linking app service after database changes"
  "${CLI[@]}" service link "$APP_SERVICE" >/dev/null
}

ensure_public_base_url() {
  if [[ -n "$PUBLIC_BASE_URL" ]]; then
    return
  fi
  if [[ "$SKIP_DOMAIN" == "1" ]]; then
    echo "PUBLIC_BASE_URL is empty and SKIP_DOMAIN=1 was set." >&2
    exit 1
  fi

  local domains_json domain_host
  domains_json="$("${CLI[@]}" domain list --service "$APP_SERVICE" --json || echo '[]')"
  if domain_host="$(printf '%s' "$domains_json" | extract_match_from_json '\.up\.railway\.app$' 2>/dev/null)"; then
    PUBLIC_BASE_URL="https://${domain_host}"
    log "Using existing Railway domain: $PUBLIC_BASE_URL"
    return
  fi

  log "Generating Railway public domain"
  "${CLI[@]}" domain --service "$APP_SERVICE" --json >/dev/null

  domains_json="$("${CLI[@]}" domain list --service "$APP_SERVICE" --json)"
  if domain_host="$(printf '%s' "$domains_json" | extract_match_from_json '\.up\.railway\.app$' 2>/dev/null)"; then
    PUBLIC_BASE_URL="https://${domain_host}"
    log "Generated Railway domain: $PUBLIC_BASE_URL"
    return
  fi

  echo "Could not determine Railway public domain for service $APP_SERVICE" >&2
  exit 1
}

generate_env_block() {
  log "Generating Railway env block at $GENERATED_ENV_FILE"
  "$PYTHON_BIN" -m app.cli export-railway-env \
    --public-base-url "$PUBLIC_BASE_URL" \
    --source-env "$SOURCE_ENV" \
    --database-mode postgres-ref \
    --output "$GENERATED_ENV_FILE" >/dev/null
}

apply_variables() {
  log "Applying service variables to $APP_SERVICE"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    "${CLI[@]}" variable set -s "$APP_SERVICE" --skip-deploys "$line" >/dev/null
  done < "$GENERATED_ENV_FILE"
}

deploy_app() {
  log "Deploying app service: $APP_SERVICE"
  "${CLI[@]}" up --service "$APP_SERVICE" --detach -y >/dev/null
}

verify_public_endpoint() {
  if [[ "$SKIP_VERIFY" == "1" ]]; then
    return
  fi

  log "Waiting for public endpoint to become ready"
  local ready_url="${PUBLIC_BASE_URL%/}/readyz"
  local ok=0
  for _ in $(seq 1 60); do
    if curl -fsS "$ready_url" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 5
  done

  if [[ "$ok" != "1" ]]; then
    echo "Timed out waiting for $ready_url" >&2
    return
  fi

  log "Public endpoint is ready; verifying MCP"
  "$PYTHON_BIN" -m app.cli verify-mcp-endpoint --url "${PUBLIC_BASE_URL%/}/" --query 삼성전자 --limit 1
}

main() {
  require_login
  ensure_project_linked
  ensure_app_service
  ensure_postgres_service
  ensure_public_base_url
  generate_env_block
  apply_variables
  deploy_app
  verify_public_endpoint

  log "Done"
  printf 'PUBLIC_BASE_URL=%s\n' "$PUBLIC_BASE_URL"
  printf 'APP_SERVICE=%s\n' "$APP_SERVICE"
  printf 'GENERATED_ENV_FILE=%s\n' "$GENERATED_ENV_FILE"
}

main "$@"
