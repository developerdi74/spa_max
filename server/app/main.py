"""
Основное приложение FastAPI.
Собирает все компоненты вместе: конфиг, репозитории, сервисы, роутеры.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, AsyncGenerator

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from maxapi import Bot

from .config.settings import settings
from .repositories.database import DatabaseManager
from .services.newsletter_service import NewsletterService
from .routers.newsletters import NewsletterRouter, HealthRouter
from .routers.shares import ShareRouter
from .utils.logging import setup_logging

logger = logging.getLogger(__name__)


# Глобальные переменные для доступа из legacy кода
db_manager: Optional[DatabaseManager] = None
newsletter_service: Optional[NewsletterService] = None
max_bot: Optional[Bot] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("🚀 Запуск приложения...")
    
    # Валидация настроек
    settings.validate()
    
    # Настройка логирования
    setup_logging(
        log_dir=settings.LOG_DIR,
        log_level=settings.LOG_LEVEL,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT
    )
    
    # Инициализация подключения к MongoDB
    global db_manager
    db_manager = DatabaseManager(settings)
    await db_manager.connect()
    
    # Сброс зависших рассылок при перезапуске
    if db_manager.newsletters:
        await db_manager.newsletters.reset_stuck_newsletters()
    
    # Инициализация бота
    global max_bot
    max_bot = Bot(token=settings.MAX_BOT_TOKEN)
    logger.info("✅ Бот MAX инициализирован")
    
    # Инициализация сервиса рассылок
    global newsletter_service
    newsletter_service = NewsletterService(
        db_manager=db_manager,
        bot=max_bot,
    )
    
    # Инициализация роутеров с зависимостями
    for router in app.state.routers:
        if isinstance(router, NewsletterRouter):
            router.initialize(db_manager, newsletter_service)
        elif isinstance(router, HealthRouter):
            router.initialize(db_manager)
        elif isinstance(router, ShareRouter):
            router.initialize(db_manager)
    
    logger.info("🚀 Webhook сервис запущен")
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка приложения...")
    
    if max_bot and hasattr(max_bot, 'session') and max_bot.session:
        await max_bot.session.close()
        logger.info("🔌 Сессия бота MAX закрыта")
    
    if db_manager:
        await db_manager.disconnect()
    
    logger.info("✅ Приложение остановлено")


def create_application() -> FastAPI:
    """Создание и настройка приложения FastAPI."""
    
    templates_path = Path(__file__).parent.parent / "templates"
    templates = Jinja2Templates(directory=str(templates_path))
    
    app = FastAPI(
        title="Renovatio Webhook Handler",
        description="Сервис обработки событий из МИС Renovatio",
        version="1.0.1",
        lifespan=lifespan,
    )
    
    # Создание роутеров
    health_router = HealthRouter()
    newsletter_router = NewsletterRouter(templates)
    share_router = ShareRouter(templates)
    
    # Сохраняем роутеры в state для последующей инициализации
    app.state.routers = [health_router, newsletter_router, share_router]
    
    # Регистрация роутеров
    app.include_router(health_router.router)
    app.include_router(newsletter_router.router)
    app.include_router(share_router.router)
    
    return app


# Создаем экземпляр приложения
app = create_application()
