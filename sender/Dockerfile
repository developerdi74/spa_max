FROM python:3.10-slim

WORKDIR /app

COPY sender/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sender/sender.py .
COPY libs /app/libs

# Если sender запускается один раз и выходит, можно оставить так.
# Если нужно планирование внутри контейнера, лучше использовать cron или внешний планировщик.
CMD ["python", "sender.py"]