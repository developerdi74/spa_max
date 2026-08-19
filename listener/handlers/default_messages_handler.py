from maxapi import Dispatcher
from maxapi.types import MessageCreated

from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.storage import MongoStorage
from listener.services.salon1c_service import Salon1CService

class DefaultMessageHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, salon1c_service: Salon1CService):
        self._storage = storage
        self._salon_service = salon1c_service
    def register(self, dp: Dispatcher) -> None:
        dp.message_created()(self.handle)

    async def handle(self, event: MessageCreated) -> None:
        validated = await self._validate_user(event, storage=self._storage, salon_service=self._salon_service)
        if validated is None:
            return
        text = as_html(
            Heading("🤖 Я — бот-помощник") +
            "\n\n" +
            "К сожалению, я не умею отвечать на произвольные вопросы." +
            "\n\n" +
            "Но я отлично помогаю записываться на процедуры и управлять визитами!" +
            "\n\n" +
            "👇 Пожалуйста, воспользуйтесь кнопками меню:"
        )
        await event.message.answer(
            text=text,         
            attachments=[Keyboards.main_menu()],
            format=Format.HTML
        )