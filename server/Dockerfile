FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервиса
COPY server/ .
COPY libs /app/libs

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]