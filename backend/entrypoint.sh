#!/bin/sh
# Автоприменение миграций при старте: ждём БД, накатываем alembic upgrade head, запускаем API.
set -e

attempt=0
until alembic upgrade head; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 20 ]; then
        echo "Миграции не применились за $attempt попыток, выход" >&2
        exit 1
    fi
    echo "БД недоступна или миграция упала (попытка $attempt/20), повтор через 3 с..."
    sleep 3
done

echo "Миграции применены"

if [ "$SEED_ON_START" = "true" ]; then
    python -m app.seed
fi

echo "Запускаю API"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
