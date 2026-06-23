#!/bin/bash
set -euo pipefail

echo "[postdeploy] Migration is handled by docker/entrypoint.sh before gunicorn starts."
echo "[postdeploy] Skipping duplicate postdeploy migration."
