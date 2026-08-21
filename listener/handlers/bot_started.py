from maxapi import Dispatcher
from maxapi.types import BotStarted
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.storage import MongoStorage
import logging

#https://max.ru/id7456020292_1_bot?start=get_in_line
class BotStartedHandler(BaseHandler):

    def __init__(self, storage: MongoStorage):
        self._storage = storage

    def register(self, dp: Dispatcher) -> None:
        dp.bot_started()(self.handle)

    async def handle(self, event: BotStarted) -> None:
        text = as_html(
            Heading("🌸 Добро пожаловать в «Другое измерение»!") +
            "\n\n" +
            "Мы рады приветствовать вас в нашем центре красоты и здоровья." +
            "\n\n" +
            "✨ Здесь вы найдете:" +
            "\n• Профессиональные процедуры" +
            "\n• Заботу о вашей красоте" +
            "\n• Атмосферу уюта и гармонии" +
            "\n\n" +
            "💫 Готовы начать свое преображение?" +
            "\n\n" +
            "👇 Нажмите на кнопку, чтобы продолжить:"
        )
        attachments = [Keyboards.main_menu()]

        phone = await self._storage.get_phone(event.chat_id)
        if not phone:
            attachments = Keyboards.request_contact()

        await event.bot.send_message(
            chat_id=event.chat_id,
            text=text,
            attachments=attachments,
            format = Format.HTML
        )