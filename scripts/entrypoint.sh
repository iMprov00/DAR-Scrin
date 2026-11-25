#!/bin/sh
set -e

echo "Ожидание PostgreSQL..."
until python - <<'PY'
import os
import sys

import psycopg

try:
    conn = psycopg.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        connect_timeout=3,
    )
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
else:
    conn.close()
    sys.exit(0)
PY
do
  sleep 1
done

echo "Применение миграций..."
python manage.py migrate --noinput

echo "Сбор статики..."
python manage.py collectstatic --noinput

echo "Запуск Gunicorn..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --timeout 60
