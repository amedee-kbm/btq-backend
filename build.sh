#!/usr/bin/env bash
# Render build step: install dependencies, collect static files, apply migrations.
# (Render's free plan has no pre-deploy hook, so migrations run here.)
set -o errexit

pip install --upgrade uv
uv sync --frozen --no-dev

cd src
uv run --no-sync python manage.py collectstatic --noinput
uv run --no-sync python manage.py migrate --noinput
