import logging

from maxapi import Dispatcher
from maxapi.filters.contact import ContactFilter
from maxapi.types.attachments.contact import Contact
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format

from libs.funcs import HelperFunction as hlp
from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.storage import MongoStorage
from listener.services.salon1c_service import Salon1CService

class ContactHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, salon1c_service: Salon1CService):
        self._storage = storage
        self._salon_service = salon1c_service

    def register(self, dp: Dispatcher) -> None:
        dp.message_created(ContactFilter())(self.handle)

    async def handle(self, event, contact: Contact) -> None:
        user_id = event.from_user.user_id
        chat_id = event.message.recipient.chat_id
        full_name = contact.payload.vcf.full_name
        phone = contact.payload.vcf.phone
        clean_phone = hlp.validate_phone(phone)
        #phone="79026001548"
        usertoken = self._salon_service.auth_client(phone)
        try:
            await self._storage.upsert_contact(
                user_id=user_id,
                chat_id=chat_id,
                phone=clean_phone,
                full_name=full_name,
                collection_name="users",
                usertoken=usertoken,
            )
        except Exception as e:
            logging.error("Ошибка при работе с MongoDB (контакт): %s", e)

        await event.message.answer(
            text = as_html(
                Heading("✅ Отлично! Вы авторизованы") +
                "\n\n" +
                "Спасибо, что поделились контактом! " +
                "Теперь вам доступны все возможности нашего бота." +
                "\n\n" +
                "✨ Что вы можете сделать:" +
                "\n• Записаться на процедуру" +
                "\n• Выбрать специалиста" +
                "\n• Просмотреть свои визиты" +
                "\n• Управлять записями" +
                "\n\n" +
                "💫 Мы рады, что вы с нами!" +
                "\n\n" +
                "👇 Выберите действие:"
            ),
            attachments=[Keyboards.main_menu()],
            format = Format.HTML
        )
