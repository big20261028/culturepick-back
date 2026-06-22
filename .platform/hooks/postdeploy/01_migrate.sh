#!/bin/bash
set -euo pipefail

echo "[postdeploy] Looking for the Elastic Beanstalk web container..."

CONTAINER_ID="$(docker ps --filter "name=current-web-1" --format "{{.ID}}" | head -n 1)"

if [ -z "$CONTAINER_ID" ]; then
  CONTAINER_ID="$(docker ps --filter "label=com.docker.compose.service=web" --format "{{.ID}}" | head -n 1)"
fi

if [ -z "$CONTAINER_ID" ]; then
  CONTAINER_ID="$(docker ps --format "{{.ID}} {{.Names}}" | awk '/web/ {print $1; exit}')"
fi

if [ -z "$CONTAINER_ID" ]; then
  echo "[postdeploy] ERROR: Could not find a running web container."
  docker ps
  exit 1
fi

echo "[postdeploy] Running Django migrations in container ${CONTAINER_ID}..."
docker exec "$CONTAINER_ID" python manage.py migrate --noinput
echo "[postdeploy] Django migrations completed."
