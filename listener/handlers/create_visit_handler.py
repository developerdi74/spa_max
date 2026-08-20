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
from listener.payloads import CreateVisitPayload, CallbackAction,VisitsActionPayload
from listener.storage import MongoStorage
from listener.utils import get_chat_id
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format
from datetime import datetime
from libs.salon1c import SalonClient, SalonAPIError, make_sign
from listener.services.salon1c_service import Salon1CService
from libs.salon1c.utils import to_iso8601

class CreateVisitHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, salon1c_service: Salon1CService):
        self._storage = storage
        self._salon_service = salon1c_service
        #http.client.HTTPConnection.debuglevel = 1
        #logging.basicConfig(level=logging.DEBUG)
        #logging.getLogger("urllib3").setLevel(logging.DEBUG)

    def register(self, dp: Dispatcher) -> None:
        dp.message_callback(CreateVisitPayload.filter(F.action == "create_visit"))(self.handle)
        #dp.message_callback(CreateVisitPayload.filter(F.action == "create_visit"))(self.handle)

    async def handle(self, event: MessageCallback, payload: CreateVisitPayload) -> None:
        logging.info(payload)
        logging.info("create_visit")
        await event.answer(
            new_text="Загрузка данных...",
            attachments=[Keyboards.menu_button()],
            format = Format.HTML           
        )

        chat_id, user_id = event.get_ids();

        validated = await self._validate_user(event, storage = self._storage, salon_service = self._salon_service)   
        if validated is None:
            return
        
        chat_id, phone, usertoken, checkuser = validated
        
        buttons=[]

        """Вывод категорий услуг"""
        if not payload.step or payload.step == "":
            text = as_html(
                Heading("🌸 Выберите категорию услуг \n\n") +
                "Каждая процедура в «Другом измерении» — это маленькое чудо преображения.\n\n" +
                "✨ Что вас интересует?"
            )
            categories = await self._salon_service.get_book_services_categories()
            for item in categories:
                title = item['title']
                buttons.append([
                    CallbackButton(
                        text=title,
                        payload=CreateVisitPayload(
                            step="get_services",
                            category_id=item['category_id']
                        ).pack()
                    )
                ])

        if payload.category_id and payload.step == "get_services":
            """Вывод услуг"""
            text = as_html(
                Heading("💫 Выберите услугу\n\n") +
                "Прекрасный выбор! В этой категории мы подготовили для вас лучшие процедуры.\n\n" +
                "✨ Какая услуга вам по душе?"
            )
            services = await self._salon_service.get_book_category_services(category_id = payload.category_id)
            for item in services:
                title = f'{item['title']} {item['price_min']}р'
                buttons.append([
                    CallbackButton(
                        text=title,
                        payload=CreateVisitPayload(
                            step="get_staff_and_date",
                            category_id=payload.category_id,
                            services_id=item['id'],
                            services_title=title
                        ).pack()
                    )
                ])

        if payload.services_id and payload.step == "get_staff_and_date":
            """Вывод мастеров и доступных дат для записи"""
            staff_id = payload.staff_id or ""
            staff = await self._salon_service.get_staff_and_date(service_id = payload.services_id, staff_id = staff_id)
            for item in staff:
                buttons=[]
                group=[]
                text = as_html(
                    Heading(f"👩‍⚕️ {item['name']}") +
                    "\n\n" +
                    "📅 Выберите удобную дату для визита:"
                )

                for available_dates in item['available_dates']:
                    format_date = datetime.fromisoformat(available_dates).strftime("%d.%m.%Y")
                    group.append(
                        CallbackButton(
                            text=format_date,
                            payload=CreateVisitPayload(
                                step="get_time_staff",
                                category_id=payload.category_id,
                                staff_id=item['id'],
                                staff_name=item['name'],
                                services_title=payload.services_title,
                                services_id=payload.services_id,
                                select_date=format_date
                            ).pack()
                        )
                    )
                    if len(group) == 3:
                        buttons.append(group)
                        group=[]
                
                if len(group) > 0 :
                    buttons.append(group)

                if not staff_id:
                    buttons.append([CallbackButton(text="Начать сначала", payload=CallbackAction(action="menu").pack())]);
                    payload_buttons = ButtonsPayload(buttons=buttons).pack()                
                    await event.send(
                        text=text,
                        attachments=[payload_buttons],
                        format = Format.HTML           
                    )
            if not staff_id:
                return
        
        if payload.staff_id and payload.step == "get_time_staff" and payload.services_id:
            """Вывод свободного времени по дате и специалисту"""
            select_date = to_iso8601(payload.select_date)
            times = await self._salon_service.get_time_staff(service_id = payload.services_id, staff_id = payload.staff_id,select_date = select_date)
            text = as_html(
                Heading(f"👩‍⚕️ {payload.staff_name}") +
                "\n\n" +
                f"Отличный выбор! {Bold(payload.select_date)} — прекрасная дата для вашего визита." +
                "\n\n" +
                "⏰ " + Bold("Выберите удобное время:") +
                "\n" +
                "Мы подготовили для вас свободные слоты:"
            )
            buttons=[]
            group=[]

            for date_str in times:
                #print(date_str)
                #time_without_seconds = date_str.split()[1][:-3]  # "12:30"
                #isotime = to_iso8601(date_str)
                group.append(
                    CallbackButton(
                        text=date_str["time"],
                        payload=CreateVisitPayload(
                            step="confirmation",
                            category_id=payload.category_id,
                            staff_id=payload.staff_id,
                            services_id=payload.services_id,
                            services_title=payload.services_title,
                            select_date=payload.select_date,
                            staff_name=payload.staff_name,
                            datetime = date_str["datetime"]
                        ).pack()
                    )
                )

                if len(group) == 5:
                    buttons.append(group)                    
                    group=[]

            ## вернуться к выбору даты
            buttons.append([
                CallbackButton(
                    text="Вернуться к выбору даты",
                    payload=CreateVisitPayload(
                        step="get_staff_and_date",
                        category_id=payload.category_id,
                        staff_id=payload.staff_id,
                        services_id=payload.services_id,
                        services_title=payload.services_title,
                        staff_name=payload.staff_name,
                        select_date="",
                        datetime = ""
                    ).pack()
                )]
            );

        if payload.staff_id and payload.step == "confirmation" and payload.services_id:
            dt = datetime.fromisoformat(payload.datetime)
            short_datetime = dt.strftime("%d.%m.%Y %H:%M")
            text = as_html(
                Heading("📋 Подтверждение записи") +
                "\n\n" +
                "Проверьте данные визита. Всё верно?" +
                "\n\n" +
                f"{Bold('💆 Услуга:')} {payload.services_title}" +
                f"\n{Bold('👩‍⚕️ Специалист:')} {payload.staff_name}" +
                f"\n{Bold('📅 Дата и время:')} {short_datetime}" +
                "\n\n" +
                "✅ Нажмите «Подтвердить», чтобы завершить запись."
            )
            buttons.append([
                CallbackButton(
                    text="Подтвердить визит", 
                    payload=CreateVisitPayload(
                            step="confirm_appointment",
                            category_id=payload.category_id,
                            staff_id=payload.staff_id,
                            services_id=payload.services_id,
                            services_title=payload.services_title,
                            select_date=payload.select_date,
                            staff_name=payload.staff_name,
                            datetime = payload.datetime
                    ).pack()
                )]
            );


        if payload.staff_id and payload.services_id and payload.datetime and payload.step == "confirm_appointment":
            #dt = datetime.strptime(payload.datetime, "%d.%m.%Y %H:%M:%S")
            print(payload.datetime)
            dt = datetime.fromisoformat(payload.datetime)
            short_datetime = dt.strftime("%d.%m.%Y %H:%M")
            text = as_html(
                Heading("✨ Запись подтверждена!") +
                "\n\n" +
                "Мы очень рады, что вы выбрали нас. Ждем вас " + Bold(short_datetime) + 
                " в центре красоты и здоровья " + Bold("«Другое измерение»") +
                "\n\n" +
                "📍 Адрес: " + Bold("ул. Ленина, 27") +
                "\n" +
                "📞 Телефон для связи: " + Bold("+7 (3519) 580-111")
            )
            format_date = to_iso8601(dt.strftime("%Y-%m-%dT%H:%M"))
            result = self._salon_service.create_visit(
                usertoken=usertoken,
                datetime_str=format_date,
                service_id=payload.services_id,
                staff_id=payload.staff_id
            )

            if result != None and result['Result'] == True:
                buttons.append([CallbackButton(text="Мои визиты", payload=VisitsActionPayload(action="list_visits").pack())]);
            else:
                text = as_html(
                    Heading("⚠️ Ошибка") +
                    "\n\n" +
                    "Произошла ошибка при создании визита. Попробуйте ещё раз."
                )
        buttons.append([CallbackButton(text="Начать сначала", payload=CallbackAction(action="menu").pack())]);

        payload_buttons = ButtonsPayload(buttons=buttons).pack()

        await event.answer(
            new_text=text,
            attachments=[payload_buttons],
            format = Format.HTML           
        )
        # await event.bot.send_message(
        #     chat_id=chat_id,
        #     text=text,
        #     format = Format.HTML,
        #     attachments=[payload_buttons]
        # )
        return