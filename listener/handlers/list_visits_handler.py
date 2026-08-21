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
from listener.payloads import CallbackAction,VisitsActionPayload
from listener.storage import MongoStorage
from listener.utils import get_chat_id
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format
from datetime import datetime
from libs.salon1c import SalonClient, SalonAPIError, make_sign
from listener.services.salon1c_service import Salon1CService

class ListVisitHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, salon1c_service: Salon1CService):
        self._storage = storage
        self._salon_service = salon1c_service

    def register(self, dp: Dispatcher) -> None:
        dp.message_callback(VisitsActionPayload.filter(F.action_filter == "list_visits"))(self.handle)

    async def handle(self, event: MessageCallback, payload: CallbackAction) -> None:
        logging.info(payload)
        logging.info("list_visits")
        text = 'Наши услуги'
        chat_id, user_id = event.get_ids();        
        phone = await self._storage.get_phone(chat_id)

        validated = await self._validate_user(event, storage = self._storage, salon_service = self._salon_service)   
        if validated is None:
            return
        
        chat_id, phone, usertoken, checkuser = validated
        buttons=[]

        if payload.action == "list_visits":
            # Асинхронный вызов
            list_visits = await self._salon_service.get_list_client_visits(usertoken=usertoken)
            if list_visits:
                for visit in list_visits:
                    print(visit)
                    buttons=[]
                    dt = datetime.fromisoformat(visit['start_date']) 
                    show_datetime = dt.strftime("%Y.%m.%d %H:%M")
                    text = as_html(
                        Heading(f"📋 Ваш активный визит\n\n") + 
                        "Информация о записи в «Другое измерение»:\n" +
                        "─" * 30 +
                        "\n",
                        f"📅 "+Bold(show_datetime)+"\n"
                    )

                    for service in visit['services']:
                        text += as_html(
                            f"💆 Услуга: "+Bold(service['service']['name'])+"\n" +
                            f"👩‍⚕️ Специалист: "+Bold(service['staff']['name'])
                        )                    
                    text += as_html(
                        "\n" +
                        "─" * 30 +
                        "\n" +
                        "❌ Нажмите «Отменить», чтобы отменить запись." +
                        "\n"
                    )
                    
                    buttons.append([
                        CallbackButton(
                            text=f"Отменить визит", 
                            payload=VisitsActionPayload(
                                action="cancel_visit", 
                                visit_id=visit['id']
                            ).pack()
                        )
                    ]);

                    payload_buttons = ButtonsPayload(buttons=buttons).pack()
                    await event.send(
                        text=text,
                        attachments=[payload_buttons],
                        format = Format.HTML
                    )
                return
            else:
                text = as_html(
                    Heading("😊 У вас пока нет запланированных визитов") +
                    "\n\n" +
                    "Но это легко исправить! Мы всегда рады видеть вас в нашем центре красоты и здоровья " + 
                    Bold("«Другое измерение»") +
                    "\n\n" +
                    "✨ Здесь вас ждут:" +
                    "\n• Профессиональный уход" +
                    "\n• Атмосфера уюта и гармонии" +
                    "\n• Индивидуальный подход к каждому гостю" +
                    "\n\n" +
                    Bold("Не откладывайте заботу о себе!") +
                    "\n" +
                    "📞 Запишитесь прямо сейчас: " + Bold("+7 (3519) 580-111") +
                    "\n📍 Мы ждем вас по адресу: " + Bold("ул. Ленина, 27")
                )
            
        if payload.action == "cancel_visit" and payload.visit_id:
            result = await self._salon_service.cancel_visit(usertoken=usertoken,record_id=payload.visit_id)
            text = as_html(
                Heading("❌ Запись отменена") +
                "\n\n" +
                "Будем рады видеть вас снова в «Другом измерении»!" +
                "\n\n" +
                "✨ Если захотите записаться заново, мы всегда на связи."
            )
            
        buttons.append([CallbackButton(text="Вернуться в главное меню", payload=CallbackAction(action="menu").pack())]);

        payload_buttons = ButtonsPayload(buttons=buttons).pack()

        await event.answer(
            new_text=text,
            attachments=[payload_buttons],
            format = Format.HTML           
        )
        return