#!/usr/bin/env bash
set -e

###
# Старт простого веб-сервера для отладочного сайта.
#
# Использование:
#   cd ~/brats/site-integration
#   ./start_debug_site.sh           # по умолчанию порт 8000
#   ./start_debug_site.sh 8080      # другой порт
#
# После запуска страница будет доступна по адресам:
#   - http://localhost:PORT/site-integration-example.html
#   - http://brats.local:PORT/site-integration-example.html (если прописан в /etc/hosts)
###

PORT="${1:-8000}"

echo "Запускаю отладочный веб-сервер для site-integration-example.html"
echo "Документ-рутом является директория: $(pwd)"
echo "Сайт будет доступен по адресам:"
echo "  - http://localhost:${PORT}/site-integration-example.html"
echo "  - http://brats.local:${PORT}/site-integration-example.html (если настроен hosts)"
echo
echo "Остановить сервер: Ctrl+C"

python -m http.server "${PORT}"












