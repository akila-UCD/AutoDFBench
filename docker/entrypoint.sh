#!/usr/bin/env bash
set -e

# Optional: print useful info
echo "[entrypoint] Using python: $(/opt/conda/envs/autodfbench/bin/python --version)"

# Run supervisor
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
