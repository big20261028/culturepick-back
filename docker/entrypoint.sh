#!/bin/sh
set -e

if [ "$1" = "gunicorn" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput

  echo "Running database migrations..."
  python manage.py migrate --noinput
elif [ "$1" = "celery" ]; then
  echo "Skipping collectstatic for non-web process..."
  echo "Waiting for database migrations..."
  for i in $(seq 1 30); do
    if python manage.py migrate --check >/dev/null 2>&1; then
      echo "Database migrations are ready."
      break
    fi

    if [ "$i" -eq 30 ]; then
      echo "ERROR: Database migrations are not ready."
      python manage.py migrate --check
      exit 1
    fi

    sleep 2
  done
fi

echo "Starting process: $1"
exec "$@"
