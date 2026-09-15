FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости
COPY admin/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервиса
COPY admin/ .
COPY libs /app/libs

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]