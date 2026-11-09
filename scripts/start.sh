#!/bin/sh
set -e

echo "==> Running database migrations with Alembic..."
alembic upgrade head

PORT="${PORT:-8000}"
echo "==> Starting DocVane FastAPI application on port ${PORT}..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1

