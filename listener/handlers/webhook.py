import logging

from maxapi import Bot, Dispatcher
from maxapi.enums.update import UpdateType

from listener.config import Config
from listener.handlers.base_handler import BaseHandler


class WebhookSetupHandler(BaseHandler):
    def __init__(self, bot: Bot, config: Config):
        self._bot = bot
        self._config = config

    def register(self, dp: Dispatcher) -> None:
        dp.on_started()(self.handle)

    async def handle(self) -> None:
        if not self._config.webhook_url:
            logging.warning("WEBHOOK_URL не задан, подписка на webhook не выполнена.")
            return

        logging.info("Диспетчер запущен, подписываемся на webhook: %s", self._config.webhook_url)
        try:
            await self._bot.subscribe_webhook(
                url=self._config.webhook_url,
                update_types=[
                    UpdateType.MESSAGE_CREATED,
                    UpdateType.MESSAGE_CALLBACK,
                    UpdateType.BOT_STARTED,
                ],
                secret=self._config.webhook_secret,
            )
            logging.info("Подписка на webhook зарегистрирована успешно.")
        except Exception as exc:
            logging.error("Не удалось зарегистрировать webhook: %s", exc)
