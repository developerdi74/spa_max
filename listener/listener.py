"""
Сервис слушает события через webhook мессенджер МАКС отправляет ответы и уведомления
Путь: /maxprojects/listener/listener.py
Библиотеки:
    /maxprojects/libs/funcs.py
    /maxprojects/libs/renovation_api.py
"""
import asyncio
import logging
import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from listener.app import ListenerApplication

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
    application = ListenerApplication()
    await application.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
