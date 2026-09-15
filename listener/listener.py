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

# Настройка логирования только для stdout (без файла)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def create_app():
    """Фабрика приложения для запуска через Gunicorn/Uvicorn."""
    application = ListenerApplication()
    # Подключение к БД выполняется в lifespan FastAPI
    return application.build_app()


if __name__ == "__main__":
    # Для прямой совместимости можно запускать через uvicorn
    import uvicorn
    uvicorn.run(
        "listener.listener:create_app",
        host="0.0.0.0",
        port=8888,
        workers=1
    )
