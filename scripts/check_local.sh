#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT}/.conda/bin/python"
NODE="${ROOT}/.conda/bin/node"
WITH_SERVICES=0
API_URL="http://127.0.0.1:8000/health"

if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python"
fi
if [[ ! -x "${NODE}" ]]; then
  NODE="node"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-services)
      WITH_SERVICES=1
      shift
      ;;
    --api-url)
      API_URL="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

run_step() {
  echo
  echo "==> $1"
  shift
  "$@"
}

cd "${ROOT}"
run_step "ruff" "${PYTHON}" -m ruff check backend/app backend/tests
run_step "mypy" "${PYTHON}" -m mypy backend/app --ignore-missing-imports
run_step "pytest" "${PYTHON}" -m pytest backend

echo
echo "==> frontend build"
(
  cd frontend
  export npm_config_cache="${ROOT}/.npm_cache"
  export PATH="${ROOT}/.conda/bin:${ROOT}/.conda:${PATH}"
  "${NODE}" node_modules/typescript/bin/tsc --noEmit
  sleep 0.5
  "${NODE}" node_modules/vite/bin/vite.js build
)

if [[ "${WITH_SERVICES}" == "1" ]]; then
  run_step "docker services" docker compose up -d postgres redis qdrant
  export DATA_BACKEND=postgres
  export REDIS_BACKEND=redis
  export KB_BACKEND=qdrant
  export DATABASE_URL=postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs
  export REDIS_URL=redis://localhost:6379/0
  export QDRANT_URL=http://localhost:6333

  if "${PYTHON}" scripts/check_health.py \
    --url "${API_URL}" \
    --expect repository_backend=postgresql \
    --expect runtime_backend=redis \
    --expect knowledge_backend=qdrant >/dev/null 2>&1; then
    run_step "health" "${PYTHON}" scripts/check_health.py \
      --url "${API_URL}" \
      --expect repository_backend=postgresql \
      --expect runtime_backend=redis \
      --expect knowledge_backend=qdrant
    exit 0
  fi

  "${PYTHON}" -m uvicorn app.api.main:app --app-dir backend --host 127.0.0.1 --port 8000 &
  BACKEND_PID=$!
  trap 'kill "${BACKEND_PID}" 2>/dev/null || true' EXIT

  for _ in $(seq 1 20); do
    sleep 1
    if "${PYTHON}" scripts/check_health.py --url "${API_URL}" >/dev/null 2>&1; then
      break
    fi
  done

  run_step "health" "${PYTHON}" scripts/check_health.py \
    --url "${API_URL}" \
    --expect repository_backend=postgresql \
    --expect runtime_backend=redis \
    --expect knowledge_backend=qdrant
fi
