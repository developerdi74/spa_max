FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY listener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY listener/ /app/listener/
COPY libs /app/libs

# Переменная окружения для количества воркеров (по умолчанию 1 для webhook)
ENV WEBHOOK_WORKERS=1

# Экспозиция порта
EXPOSE 8888

# Запуск через gunicorn с uvicorn workers
# ВАЖНО: Для webhook используем 1 воркер, чтобы избежать проблем с регистрацией хендлеров
CMD ["gunicorn", "listener.listener:create_app", "-b", "0.0.0.0:8888", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "--access-logfile", "-", "--error-logfile", "-", "--capture-output"]