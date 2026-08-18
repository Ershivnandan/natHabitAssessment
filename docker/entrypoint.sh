#!/usr/bin/env bash
set -euo pipefail

# The API container owns schema migrations; worker/beat containers set
# RUN_MIGRATIONS=0 so migrations run exactly once on startup.
if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
    echo "Applying database migrations..."
    alembic upgrade head
fi

exec "$@"
