"""
Сервис слушает события через webhook мессенджер МАКС отправляет ответы и уведомления
Путь: /spamaxbot/listener/listener.py
Библиотеки:
    /maxprojects/libs/funcs.py
    /maxprojects/libs/salon1c
"""
import asyncio
import logging
import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from listener.app import ListenerApplication, create_app
from fastapi import FastAPI
import uvicorn

#logging.basicConfig(level=logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

async def main():
    # Запускаем через uvicorn с factory-функцией для поддержки lifespan
    config = uvicorn.Config(
        app="listener.listener:create_app",
        factory=True,
        host="0.0.0.0",
        port=8888,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
