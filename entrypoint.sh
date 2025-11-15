#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput

exec gunicorn "${DJANGO_WSGI_MODULE:-project.wsgi:application}" \
    --bind "${GUNICORN_BIND:-0.0.0.0:8000}" \
    ${GUNICORN_EXTRA_ARGS:-}
