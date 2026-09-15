import logging
import re
import http.client

from maxapi import Dispatcher, F
from maxapi.types import MessageCallback
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import CallbackButton

from libs.funcs import HelperFunction as hlp
from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.payloads import CreateVisitPayload, CallbackAction,ConfirmAppointmentPayload
from listener.storage import MongoStorage
from listener.utils import get_chat_id
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format
from datetime import datetime
from libs.salon1c import SalonClient, SalonAPIError, make_sign
from listener.services.salon1c_service import Salon1CService, SalonServiceError
from libs.salon1c.utils import to_iso8601

class CreateVisitHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, salon1c_service: Salon1CService):
        self._storage = storage
        self._salon_service = salon1c_service
        #http.client.HTTPConnection.debuglevel = 1
        #logging.basicConfig(level=logging.DEBUG)
        #logging.getLogger("urllib3").setLevel(logging.DEBUG)

    def register(self, dp: Dispatcher) -> None:
        dp.message_callback(ConfirmAppointmentPayload.filter(F.action == "confirmation"))(self.handle)

    async def handle(self, event: MessageCallback, payload: ConfirmAppointmentPayload) -> None:
        logging.info(payload)
        logging.info("confirm_visit")
        """await event.answer(
            new_text="Обработка...",
            attachments=[Keyboards.menu_button1()],
            format = Format.HTML           
        )"""

        validated = await self._validate_user(event, storage = self._storage, salon_service = self._salon_service)   
        if validated is None:
            return        
        chat_id, phone, usertoken, checkuser = validated
        
        buttons=[]
        buttons.append(Keyboards.menu_button())
        payload_buttons = ButtonsPayload(buttons=buttons).pack()

        appointment_id = payload.appointment_id
        logging.info(f"Подтверждение визита {appointment_id} US: "+ usertoken)
        if not appointment_id:
            text = "Не удалось подтвердить визит"
        else:
            result = await self._salon_service.confirm_visit(appointment_id=appointment_id)
            await self._storage.add_confirmations(phone=phone)
        """await event.answer(
            new_text=text,
            attachments=[payload_buttons],
            format = Format.HTML           
        )"""
        return
    