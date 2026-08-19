FROM python:3.10-slim

WORKDIR /app

COPY listener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listener/ /app/listener/
COPY libs /app/libs

CMD ["python", "listener/listener.py"]