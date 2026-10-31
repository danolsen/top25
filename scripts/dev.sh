#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

docker compose up -d db mailpit

echo "Waiting for Postgres..."
ready=0
for _ in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U top25 -d top25 >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "Postgres did not become ready." >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
elif [[ -x "$ROOT/.tools/bin/uv" ]]; then
  UV="$ROOT/.tools/bin/uv"
else
  echo "Run make setup first so uv is available." >&2
  exit 1
fi

(cd backend && "$UV" run alembic upgrade head)

cleanup() {
  if [[ -n "${BACK_PID:-}" ]]; then
    kill "$BACK_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONT_PID:-}" ]]; then
    kill "$FRONT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

(cd backend && "$UV" run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACK_PID=$!
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) &
FRONT_PID=$!

echo "App http://localhost:5173"
echo "API http://localhost:8000"
echo "Mailpit http://localhost:8025"
wait
