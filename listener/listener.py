"""
Сервис слушает события через webhook мессенджер МАКС отправляет ответы и уведомления
Путь: /spamaxbot/listener/listener.py
Библиотеки:
    /maxprojects/libs/funcs.py
    /maxprojects/libs/salon1c
"""
import logging
import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from listener.app import ListenerApplication

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Создаем экземпляр приложения для использования в uvicorn
application = ListenerApplication()
app = application.build_app()
