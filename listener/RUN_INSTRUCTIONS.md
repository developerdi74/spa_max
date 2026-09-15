# Запуск через Uvicorn (для разработки)
uvicorn listener.listener:create_app --host 0.0.0.0 --port 8888 --reload

# Запуск через Uvicorn с несколькими воркерами (для продакшена)
uvicorn listener.listener:create_app --host 0.0.0.0 --port 8888 --workers 4

# Запуск через Gunicorn с Uvicorn workers (рекомендуется для продакшена)
gunicorn listener.listener:create_app -b 0.0.0.0:8888 -k uvicorn.workers.UvicornWorker -w 4 --access-logfile - --error-logfile - --capture-output

# Запуск через Docker
docker build -t listener-bot .
docker run -p 8888:8888 --env-file .env listener-bot

# Переменные окружения для настройки количества воркеров в Docker
# WEBHOOK_WORKERS=4
