"""
FastAPI сервис для обработки webhook-событий из МИС Renovatio. Принимает входящие вебхуки по URL /event отправляет уведомления по разным событиям
Путь: /server/start.py

Этот файл обеспечивает обратную совместимость со старой структурой.
Для нового кода рекомендуется использовать app/main.py
"""
import sys
from pathlib import Path

# Добавляем родительскую директорию в path для импортов
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Импортируем приложение из новой модульной структуры
from app.main import app

# Для обратной совместимости экспортируем ключевые компоненты
from app.main import db_manager, newsletter_service, max_bot
from app.config.settings import settings
from app.models.newsletter import NewsletterStatus

logger = __import__('logging').getLogger(__name__)


if __name__ == "__main__":
    import uvicorn
    host = settings.WEBHOOK_HOST
    port = settings.WEBHOOK_PORT
    logger.info(f"🔧 Запуск сервера на {host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.is_development,
        log_level="info"
    )
