#!/bin/bash
# Скрипт для запуска KB Service

cd "$(dirname "$0")"

# Проверяем наличие config.env
if [ ! -f "config.env" ]; then
    echo "⚠️  config.env не найден. Копирую из примера..."
    cp config.env.example config.env
    echo "✅ Создан config.env. Отредактируйте его перед запуском!"
    exit 1
fi

# Запускаем сервис
echo "🚀 Запуск KB Service..."
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

















