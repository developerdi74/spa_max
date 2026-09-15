FROM python:3.10-slim

WORKDIR /app

COPY listener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listener/ /app/listener/
COPY libs /app/libs

EXPOSE 8888

CMD ["uvicorn", "listener.listener:create_app", "--host", "0.0.0.0", "--port", "8888", "--factory"]