#!/bin/bash
set -e

DB_PATH=/data/tradle.db

# Restore database from Tigris if it exists and local doesn't
if [ ! -f "$DB_PATH" ]; then
  echo "Restoring database from Tigris..."
  litestream restore -if-replica-exists -o "$DB_PATH" "$DB_PATH"
fi

# Start litestream with gunicorn as subprocess
exec litestream replicate -exec "gunicorn --bind 0.0.0.0:8080 --workers 1 backend.app:app"
