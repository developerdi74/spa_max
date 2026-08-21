from maxapi import Dispatcher
from maxapi.types import MessageCallback,Message
from listener.utils import get_chat_id
from libs.funcs import HelperFunction as hlp
from listener.keyboards import Keyboards
from listener.storage import MongoStorage
from libs.salon1c import SalonClient, SalonAPIError, make_sign
from listener.services.salon1c_service import Salon1CService
import logging

class BaseHandler:
    _registry = []    
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Добавляем в реестр все дочерние классы
        BaseHandler._registry.append(cls)

    def register(self, dp: Dispatcher) -> None:
        raise NotImplementedError

    async def _validate_user(self, event: Message, storage: MongoStorage, salon_service: Salon1CService) -> tuple[str, str, str, list] | None:
        """Валидация chat_id и телефона (асинхронно)"""
        chat_id = get_chat_id(event)
        if not chat_id:
            logging.error("Не удалось получить chat_id")
            return None

        chat_info = await storage.get_record_by_chat_id(chat_id)        

        phone = chat_info.get("phoneNumber", "") if chat_info else ""
        phone = hlp.validate_phone(phone)

        usertoken = chat_info.get("usertoken", "") if chat_info else ""

        # Асинхронная проверка токена
        checkuser = await salon_service.validity_usertoken(usertoken)

        if phone and checkuser == False:
            # Асинхронная авторизация
            usertoken = await salon_service.auth_client(phone)
            await storage.update_usertoken(phone=phone, usertoken=usertoken)

        if not chat_info or not phone or not usertoken:
            await event.send(
                text="Для продолжения работы, пожалуйста, поделитесь контактом.",
                attachments=Keyboards.request_contact()
            )
            return None
        
        return chat_id, phone, usertoken, checkuser


class HandlerRegistry:
    def __init__(self, handlers: list[BaseHandler]):
        self._handlers = handlers

    def register_all(self, dp: Dispatcher) -> None:
        for handler in self._handlers:
            handler.register(dp)
