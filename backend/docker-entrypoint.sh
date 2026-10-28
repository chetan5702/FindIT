#!/bin/sh
set -eu

if [ "${FINDIT_AUTO_MIGRATE:-true}" = "true" ]; then
    alembic upgrade head
fi
exec "$@"

