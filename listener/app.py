import logging
import inspect
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from maxapi import Bot, Dispatcher
from maxapi.webhook.fastapi import FastAPIMaxWebhook
from listener.handlers import discover_handlers, HandlerRegistry

# Явно загружаем переменные окружения ДО импорта Config
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from listener.config import Config
from listener.services.salon1c_service import Salon1CService
from listener.storage import MongoStorage
from listener.services.aihelper_service import AIHelperService 
from libs.salon1c import SalonClient, SalonAPIError, make_sign


# Глобальное хранилище экземпляра приложения для factory-функции
_app_instance: "ListenerApplication | None" = None


@asynccontextmanager
async def _lifespan_manager(app: FastAPI):
    """Глобальный менеджер жизненного цикла для uvicorn --factory
    
    Использует глобальный экземпляр приложения, созданный в create_app()
    Работает как асинхронный генератор для поддержки startup/shutdown.
    """
    global _app_instance
    if _app_instance is None:
        logging.error("Lifespan запущен, но _app_instance не инициализирован!")
        yield
        return
    
    # Startup - подключаем ресурсы ПЕРЕД обработкой запросов
    try:
        logging.info("Запуск подключения к MongoDB...")
        await _app_instance._connect_resources()
        logging.info("MongoDB подключен успешно")
    except Exception as e:
        logging.error(f"Ошибка подключения к MongoDB: {e}")
        logging.warning("Приложение запущено без подключения к MongoDB")
    
    yield  # Передаем управление приложению
    
    # Shutdown - отключаем ресурсы после остановки приложения
    logging.info("Остановка приложения, отключение MongoDB...")
    await _app_instance._disconnect_resources()
    logging.info("MongoDB отключен")


class ListenerApplication:
    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self.bot = Bot()

        self.dp = Dispatcher()

        # Создаем storage СРАЗУ при инициализации
        self.storage = MongoStorage(self.config.mongo_uri, self.config.db_name, self.config.collection_name)
        self.salon1c_service = Salon1CService(api_key=self.config.salon_key, salon_id=self.config.salon_id, usertoken_app=self.config.usertoken_app)
        self.aihelper_service = AIHelperService(self.config.ai_key, self.config.ai_url, self.config.ai_project, self.config.ai_model)

        self._app = None
        # Хендлеры регистрируем ПОСЛЕ создания storage, но connect вызывается в lifespan
        self._register_handlers()

    def _register_handlers(self) -> None:
        # 1. Автоматически находим все классы хендлеров
        handler_classes = discover_handlers()
        
        # 2. Пул всех доступных зависимостей
        deps = {
            'storage': self.storage,
            'bot': self.bot,
            'config': self.config,
            'salon1c_service': self.salon1c_service,
            'aiservice': self.aihelper_service
        }
        
        # 3. Динамически создаем экземпляры
        instances = []

        EXCLUDED_HANDLERS = []
        logging.info(self.config.ai_activated)
        
        if self.config.ai_activated != "1":
            EXCLUDED_HANDLERS.append("AiAnswerHandler")
        else:            
            EXCLUDED_HANDLERS.append("DefaultMessageHandler")

        for cls in handler_classes:
            if cls.__name__ in EXCLUDED_HANDLERS:
                logging.info(f"Пропущен хендлер: {cls.__name__}")
                continue
            sig = inspect.signature(cls.__init__)
            kwargs = {k: v for k, v in deps.items() if k in sig.parameters}
            instances.append(cls(**kwargs))
            
        # 4. Регистрируем
        registry = HandlerRegistry(instances)
        registry.register_all(self.dp)

    async def _connect_resources(self) -> None:
        """Подключение к MongoDB при старте приложения."""
        await self.storage.connect()
        logging.info("MongoDB подключен успешно")

    async def _disconnect_resources(self) -> None:
        """Отключение от MongoDB при остановке приложения."""
        self.storage.close()
        logging.info("MongoDB отключен")

    def build_app(self) -> FastAPI:
        if self._app is not None:
            return self._app
        
        webhook = FastAPIMaxWebhook(
            dp=self.dp,
            bot=self.bot,
            secret=self.config.webhook_secret,
        )

        app = FastAPI(
            title="MaxAPI Webhook Listener Bot",
            lifespan=_lifespan_manager,  # Используем глобальный lifespan
        )

        webhook.setup(app, path=self.config.webhook_path)

        @app.get("/healthz")
        async def healthz() -> JSONResponse:
            return JSONResponse({
                "status": "ok",
                "webhook_path": self.config.webhook_path,
            })

        self._app = app
        return app

    async def run(self) -> None:
        app = self.build_app()
        config = uvicorn.Config(
            app=app,
            host=self.config.webhook_host,
            port=self.config.webhook_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        logging.info(
            "Запуск webhook-сервера на %s:%d%s",
            self.config.webhook_host,
            self.config.webhook_port,
            self.config.webhook_path,
        )

        try:
            await server.serve()
        except KeyboardInterrupt:
            logging.info("Получен сигнал остановки бота...")


def create_app() -> FastAPI:
    """Factory function for uvicorn --factory
    
    Эта функция создает экземпляр приложения и сохраняет его глобально,
    чтобы lifespan мог получить доступ к ресурсам (MongoDB).
    Переменные окружения уже загружены при импорте модуля.
    """
    global _app_instance
    
    application = ListenerApplication()
    _app_instance = application
    return application.build_app()
