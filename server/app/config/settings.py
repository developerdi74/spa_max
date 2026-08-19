"""
Конфигурация приложения.
Централизованное управление настройками через переменные окружения.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, find_dotenv

# Загружаем переменные окружения
load_dotenv(find_dotenv())


class Settings:
    """Настройки приложения."""
    
    # MongoDB настройки
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "spa_max")
    COLLECTION_USERS: str = os.getenv("COLLECTION_NAME", "users")
    COLLECTION_SENDER: str = os.getenv("COLLECTION_SENDER", "sender")
    COLLECTION_NEWSLETTERS: str = os.getenv("COLLECTION_NEWSLETTERS", "newsletters")
    COLLECTION_NEWSLETTERS_LOGS: str = os.getenv("COLLECTION_NEWSLETTERS_LOGS", "newsletters_logs")
    
    # MAX Bot настройки
    MAX_BOT_TOKEN: str = os.getenv("MAX_BOT_TOKEN", "")
    
    # Salon1C настройки
    SALON_API_KEY: str = os.getenv("SALON_API_KEY", "")
    SALON_ID: str = os.getenv("SALON_ID", "")
    
    # Сервер настройки
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENV", "production")
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = Path(__file__).parent.parent.parent / "logs"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5
    
    # Рассылки
    NEWSLETTER_RATE_LIMIT_DELAY: float = 0.05  # задержка между сообщениями (сек)
    NEWSLETTER_BATCH_SIZE: int = 10  # обновление статистики каждые N сообщений
    
    @property
    def is_development(self) -> bool:
        """Проверка режима разработки."""
        return self.ENVIRONMENT != "production"
    
    def validate(self) -> None:
        """Валидация обязательных настроек."""
        if not self.MAX_BOT_TOKEN:
            raise ValueError("MAX_BOT_TOKEN is required in .env")
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI is required in .env")


# Глобальный экземпляр настроек
settings = Settings()
