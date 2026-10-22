#!/usr/bin/env bash
# Reproducible integration gate; destructive cleanup is restricted to a unique,
# ephemeral Docker Compose project created by this script.
set -euo pipefail
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo 'ERROR: Docker Engine and docker compose v2 are required for PostgreSQL integration.' >&2
  exit 3
fi
LAB_NAME="agent_reliability_$(date +%s)_$$"
if [[ ! "$LAB_NAME" =~ ^[a-z][a-z0-9_]{5,60}$ ]]; then
  echo 'ERROR: Invalid project name. Use lowercase letters, numbers, underscores.' >&2
  exit 4
fi
COMPOSE=(docker compose -p "$LAB_NAME" -f docker-compose.yml -f docker-compose.v2.yml -f docker-compose.integration.yml)
cleanup() {
  code=$?
  trap - EXIT
  if (( code != 0 )); then
    echo '--- Failed PostgreSQL / simulator service logs ---' >&2
    "${COMPOSE[@]}" logs --tail 120 postgres servicenow-simulator >&2 || true
  fi
  if [[ "${RELIABILITY_LAB_KEEP:-0}" != '1' ]]; then
    "${COMPOSE[@]}" down --remove-orphans --volumes || true
  else
    echo "Lab retained for inspection: ${LAB_NAME}" >&2
  fi
  exit "$code"
}
trap cleanup EXIT
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up -d --build --wait postgres servicenow-simulator
"${COMPOSE[@]}" --profile integration run --build --rm reliability-tests
