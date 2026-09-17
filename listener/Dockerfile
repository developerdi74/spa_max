FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY listener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listener/ /app/listener/
COPY libs /app/libs

EXPOSE 8888

CMD ["uvicorn", "listener.listener:app", "--host", "0.0.0.0", "--port", "8888"]