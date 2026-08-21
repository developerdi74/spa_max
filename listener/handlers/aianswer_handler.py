from maxapi import Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback
from listener.handlers.base_handler import BaseHandler
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import CallbackButton, LinkButton
from listener.keyboards import Keyboards
from listener.services import AIHelperService
import logging
import json
from libs.funcs import HelperFunction as hlp
from rich import print as rprint
from listener.storage import MongoStorage
from datetime import datetime, timedelta
from listener.payloads import CallbackAction, CreateVisitPayload,VisitsActionPayload
from typing import List, Optional, Any
from maxapi.filters.contact import ContactFilter
from libs.salon1c import SalonClient, SalonAPIError, make_sign
from listener.services.salon1c_service import Salon1CService
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format

MESSAGES_INFO="""
Чтобы сэкономить ваше время, просто уточните, что именно вас интересует:
• Запись к конкретному врачу (назовите ФИО);
• Подбор по специальности;
• Цена на услугу;
• История ваших визитов;
• Информация о центрах и адресах.

Напишите ключевое слово или вопрос — и бот постарается помочь или воспользуйтесь меню.
"""
SYSTEM_PROMT = """
Ты — Entity Extractor центра красоты и здоровья Другое измерение. Извлекай данные из сообщений для поиска категорий, специалистов и услуг.
ПРАВИЛА:
Возвращай ТОЛЬКО валидный JSON. Без markdown (```json), пояснений, приветствий и советов.
Обязательно исправляй ошибки и опечатки русского языка, пиши правильно. Если данных нет — используй null или []. Не выдумывай.
Сопоставляй симптомы со специальностями. Если неясно — направляй в "терапию" (key_words_category).
Если спрашивают об услуге/специальности, в "text" давай краткую справку.
СТРУКТУРА JSON:
{
"text": "Ответ пациенту: справка, запрос уточнений или подтверждение.",
"intent": "find_doctor | find_category | book_appointment | info_request | cancel_appointment | find_services | information_centers | info_visit | info_docs | documents | operator",
"key_words_doctor": ["ТОЛЬКО фамилия врача в именительном падеже (м/ж род)"],
"key_words_category": ["Множественное, специальности (терапия, кардиология, узи)"],
"key_words_services": ["Множественное, выяви слова по которым можно найти услугу по ключевым словам в её названии в мужском роде в единственном числе, учитывай все возможные названия и сокрещения(УЗИ, ФГС и т.п)"],
"is_ambiguous": "1, если запрос размыт ('хочу к врачу', 'плохо')"
"spam": "1, если просто спам"
}
ПРИОРИТЕТ INTENT:
Если вопросе указан специалист, фамилия или обнаружил фамилию, в этих случаях только intent -> "find_doctor"
Указана или определена из контекста специальность/направление требуется или записаться к специалисту -> "find_category"
"Запиши/бронь" без указанной специальности, врача, фамилии и не возможно определить специальность-> "info_request" (text: "Уточните специальность или врача")
Вопрос кто лечит/что делать кратко объяснить в text, подсказать специальность -> "info_request"
Адреса/контакты клиники -> "information_centers"
Отмена/изменение своих записей -> "info_visit"
Получение анализов/документов -> "info_docs"
Стоимость услуг -> "find_services"
Скачать/получить документы или анализы -> "documents"
Хочет связаться с оператором или колл-центром-> "operator"

ПРИМЕРЫ:
Вход: "Хочу к Петровой на завтра"
{"text":"Нашел специалистов по вашему запросу", "intent":"find_doctor", "key_words_doctor":["Петрова"], "key_words_category":[],"key_words_services":[], "is_ambiguous":0}
Вход: "Записаться на визаж?"
{"text":"Нашел подходящие категории", "intent":"find_category", "key_words_doctor":[], "key_words_category":["Визаж"], "key_words_services":[], "is_ambiguous":0}
Вход: "На стрижку"
{"text":"Услуги которые я нашел", "intent":"find_services","key_words_doctor":[], "key_words_category":[""],"key_words_services":["стрижка"], "is_ambiguous":0}
Вход: "Услуги для отдыха"
{"text":"Вот что могу вам предложить", "intent":"find_services", "key_words_doctor":[], "key_words_category":["уход"], "key_words_services":["массаж","термальный комплекс", "хаммам"], "is_ambiguous":0}
Вход: "Как к вам записаться"
{"text":"Для записи воскользуйтесь меню ниже", "intent":"find_services", "key_words_doctor":[], "key_words_category":[""], "key_words_services":["ультразвук","почка","почек"], "is_ambiguous":0}
"""


class AiAnswerHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, aiservice: AIHelperService, salon1c_service: Salon1CService):
        self._storage = storage
        self._service = aiservice
        self._salon_service = salon1c_service
        self._aiclient = self._service.connect_to_ai()

    def register(self, dp: Dispatcher) -> None:
        dp.message_created(F.message.body.text.len() <= 5)(self.more_info)
        dp.message_created(F.message.body.text.len() >= 6)(self.handle)

    async def handle(self, event: MessageCreated) -> None:
        validated = await self._validate_user(event, storage = self._storage, salon_service = self._salon_service)   
        if validated is None:
            return
        
        chat_id, phone, usertoken, checkuser = validated
        
        new_msg = await event.message.answer(
            text="Думаю...",
            attachments=[Keyboards.menu_button1()],
            format = Format.HTML 
        )
        
        print(new_msg)
        message = event.message.body.text or ""
        await self._storage.insert_message(phone=phone,message_client=message)
        
        #Собираем промт
        messages=[]
        conversation_history=[]
        conversation_history.append({
            "role": "system",
            "content": SYSTEM_PROMT
        })
        conversation_history.extend(await self.get_history_user_message(phone=phone))
        #добавляем новое сообщение
        conversation_history.append({
            "role": "user",
            "content": message
        })
        #отправляем сообщение ИИ для разбора
        cleaned_request = await self._service.clean_json_response(messages=conversation_history)
        #hlp.log_json(cleaned_request)
        logging.info(cleaned_request)

        text = "Вот что я нашел"
        buttons = []
        try:
            json_data = json.loads(cleaned_request)
            intent = json_data.get("intent", "intent_none")
            key_words_services = json_data.get("key_words_services", [])
            key_words_category = json_data.get("key_words_category", [])
            key_words_doctor = json_data.get("key_words_doctor", [])
            #key_words_category = [cat for cat in key_words_category if cat and cat.strip()]
            text = json_data.get("text", "Пожалуйста, уточните вопрос или воспользуйтесь меню")
            #await self._storage.insert_message(phone=phone,message_ai=text)
            items = None
            if isinstance(json_data, dict):
                if key_words_doctor:
                    text="Какая услуга вас интересует?"

                if key_words_category:
                    all_categories = await self._salon_service.get_book_services_categories()
                    categories = await self._service.get_categories(all_categories, key_words_category)
                    if categories:
                        text = "Категории по вашему запросу:"
                        for category in categories:
                            buttons.append([
                                CallbackButton(
                                    text=category.get("title"), 
                                    payload=CreateVisitPayload(
                                        step="get_services",
                                        category_id=category.get("category_id")
                                    ).pack()
                                )]                          
                            )

                if key_words_services:
                    all_services = await self._salon_service.get_book_services()
                    services = await self._service.get_services(all_services, key_words_services)
                    if services:                        
                        text = "Услуги по вашему запросу:"
                        for service in services:
                            buttons.append([
                                CallbackButton(
                                    text=service.get("title"), 
                                    payload=CreateVisitPayload(
                                        step="get_staff_and_date",
                                        services_id=service.get("id"),
                                        category_id=service.get("category")['id'],
                                        services_title=service.get("title"),
                                    ).pack()
                                )]                          
                            )

                if intent == "info_request":
                    text = text
                elif intent == "information_centers":
                    text = "Всю информацию о наших центра вы можете получить нажав на кнопку ниже"
                    buttons = [[CallbackButton(text="Информация о центрах", payload=CallbackAction(action="information_centers").pack())]]
                elif intent == "info_visit":
                    text = "Всю информацию о ваших визитах вы можете получить нажав на кнопку 'Мои визиты'"
                    buttons = [[CallbackButton(text="Мои визиты", payload=VisitsActionPayload(action="list_visits").pack())]]
                elif intent == "documents":
                    text = "Информация по вашим документам вы можете получить нажав на кнопку 'Анализы и документы'"
                    buttons = [[CallbackButton(text="Анализы и документы", payload=CallbackAction(action="personal").pack())]]
                elif intent == "operator":
                    text = "Чтобы задать вопрос оператору, пожалуйста, перейдите в канал нашего колл-центра"
                    buttons = [[LinkButton(text="Колл-центр", url="https://max.ru/id7456020292_bot")]]
            else:
                text=MESSAGES_INFO

        except json.JSONDecodeError as e:
            logging.error(f"JSON parse error: {e}")
            text=MESSAGES_INFO
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            text = "Произошла ошибка. Пожалуйста, попробуйте позже или воспользуйтесь меню."

        buttons.append(Keyboards.menu_button());

        attachs = [ButtonsPayload(buttons=buttons).pack()]
        await event.message.answer(
            text=text or "Нашел такую информацию",
            attachments=attachs,
        )

    async def more_info(self, event: MessageCreated) -> None:
        """Событие если сообщение короткое"""
        message = event.message.body.text
        text = MESSAGES_INFO
        buttons = []
        buttons.append(Keyboards.menu_button());
        payload_buttons = ButtonsPayload(buttons=buttons).pack()
        attachs = [payload_buttons]
        await event.message.answer(
            text=text,
            attachments=attachs,
        )

    async def get_history_user_message(self, phone:str) ->List[dict]:
        today = datetime.now()
        conversation_history=[]
        messages = await self._storage.get_user_messages(phone=phone, limit=4, date=today)
        for m in messages:
            if m['message_client']:
                conversation_history.append({
                    "role": "user",
                    "content": m['message_client']
                })
            if m['message_ai']:
                conversation_history.append({
                    "role": "assistant",
                    "content": m['message_ai']
                })
        return conversation_history
    
    def renderKeyBoard(self, items:List[dict],type:int):
        buttons = []
        for item in items: 
            profession_id = str(item.get('profession')[0])
            user_id = str(item["id"])
            text = item.get('title') or item.get('name')
            action="get_services"
            buttons.append([
                CallbackButton(
                    text=text,
                    payload=CallbackAction(
                        action="get_user_time"
                    ).pack()
                )]
            )
        return buttons