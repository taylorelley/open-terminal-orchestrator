#!/bin/sh
set -e

echo "Running database migrations..."
cd /app/backend && python -m alembic upgrade head
echo "Migrations complete."

exec oto
