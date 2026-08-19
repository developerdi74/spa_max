FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервиса
COPY server/start.py .
COPY libs /app/libs

CMD ["uvicorn", "start:app", "--host", "0.0.0.0", "--port", "8000"]