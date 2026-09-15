import logging
import inspect
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from maxapi import Bot, Dispatcher
from maxapi.webhook.fastapi import FastAPIMaxWebhook
from listener.handlers import discover_handlers, HandlerRegistry

from listener.config import Config
from listener.services.salon1c_service import Salon1CService
from listener.storage import MongoStorage
from listener.services.aihelper_service import AIHelperService 
from libs.salon1c import SalonClient, SalonAPIError, make_sign


class ListenerApplication:
    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self.bot = Bot()

        self.dp = Dispatcher()

        self.storage = MongoStorage(self.config.mongo_uri, self.config.db_name, self.config.collection_name)
        self.salon1c_service = Salon1CService(api_key=self.config.salon_key, salon_id=self.config.salon_id, usertoken_app=self.config.usertoken_app)
        self.aihelper_service = AIHelperService(self.config.ai_key, self.config.ai_url, self.config.ai_project, self.config.ai_model)

        self._register_handlers()

    def _register_handlers(self) -> None:
        # 1. Автоматически находим все классы хендлеров
        handler_classes = discover_handlers()
        
        logging.info("Найдено хендлеров: %d", len(handler_classes))
        for cls in handler_classes:
            logging.info("  - %s", cls.__name__)
        
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
        logging.info("AI активирован: %s", self.config.ai_activated)
        
        if self.config.ai_activated != "1":
            EXCLUDED_HANDLERS.append("AiAnswerHandler")
            logging.info("Исключен хендлер: AiAnswerHandler (AI не активирован)")
        else:            
            EXCLUDED_HANDLERS.append("DefaultMessageHandler")
            logging.info("Исключен хендлер: DefaultMessageHandler (AI активирован)")

        for cls in handler_classes:
            if cls.__name__ in EXCLUDED_HANDLERS:
                logging.info("Пропущен хендлер: %s", cls.__name__)
                continue
            sig = inspect.signature(cls.__init__)
            kwargs = {k: v for k, v in deps.items() if k in sig.parameters}
            instances.append(cls(**kwargs))
            logging.info("Зарегистрирован хендлер: %s", cls.__name__)
            
        # 4. Регистрируем
        registry = HandlerRegistry(instances)
        registry.register_all(self.dp)
        logging.info("Всего зарегистрировано хендлеров: %d", len(instances))

    def build_app(self) -> FastAPI:
        webhook = FastAPIMaxWebhook(
            dp=self.dp,
            bot=self.bot,
            secret=self.config.webhook_secret,
        )

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Подключение к БД при старте
            await self.storage.connect()
            logging.info("Подключение к MongoDB установлено")
            
            # Логирование зарегистрированных обработчиков после подключения
            logging.info("=== Зарегистрированные обработчики событий ===")
            event_handlers = {
                'message_created': len(self.dp.event_handlers),
                'message_callback': len([h for h in self.dp.event_handlers if hasattr(h, 'filters')]),
            }
            logging.info("Всего обработчиков событий: %d", len(self.dp.event_handlers))
            
            yield
            
            # Отключение при остановке
            self.storage.close()
            logging.info("Подключение к MongoDB закрыто")

        app = FastAPI(
            title="MaxAPI Webhook Listener Bot",
            lifespan=lifespan,
        )

        webhook.setup(app, path=self.config.webhook_path)

        @app.get("/healthz")
        async def healthz() -> JSONResponse:
            return JSONResponse({
                "status": "ok",
                "webhook_path": self.config.webhook_path,
            })

        return app

    async def run(self) -> None:
        """Метод для обратной совместимости, но теперь используется lifespan."""
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
        finally:
            self.storage.close()
            logging.info("Бот и ресурсы успешно остановлены.")
