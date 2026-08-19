"""
Сервис слушает события пуллингом мессенджер МАКС отправляет ответы и уведомления
Путь: /maxprojects/listener/listener.py
Библиотеки: 
    /maxprojects/libs/funcs.py
    /maxprojects/libs/renovation_api.py
"""
import asyncio
import logging
import sys
import os

from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from libs.funcs import HelperFunction as hlp

from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from maxapi import Bot, Dispatcher, F
from maxapi.types import BotStarted, MessageCreated, MessageCallback, UserAdded
from motor.motor_asyncio import AsyncIOMotorClient
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import RequestContactButton, CallbackButton
from maxapi.filters.contact import ContactFilter
from maxapi.types.attachments.contact import Contact
from libs.renovation_api import RenovatioClient
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import (ClipboardButton,LinkButton,CallbackButton)
from datetime import datetime,timedelta

logging.basicConfig(level=logging.INFO)
load_dotenv(find_dotenv())

# Инициализация бота и диспетчера
bot = Bot()
dp = Dispatcher()

# Глобальная переменная для клиента MongoDB
mongo_client = None
db = None
collection = None

mis_client = None 

class ConfirmAppointment(CallbackPayload, prefix='confirmAppointment'):
    appointment_id: str
    action: str
    
class CallbackAction(CallbackPayload, prefix='visits'):
    action: str

async def init_mongo():
    global mongo_client, db, collection, MIS_API_URL, MIS_API_KEY
    mongo_client = AsyncIOMotorClient(os.getenv("MONGO_URI")) # Обновленный адрес подключения
    db = mongo_client[os.getenv("DB_NAME")]
    collection = db[os.getenv("COLLECTION_NAME")]
    MIS_API_URL = os.getenv("MIS_API_URL")
    MIS_API_KEY = os.getenv("MIS_API_KEY")

async def getPhone(chat_id: int):
    record = await collection.find_one({"chatId": chat_id})
    if not record:
        return False;
    phone_number = (record.get("phoneNumber"))
    if not phone_number:
        return False    
    return phone_number


@dp.bot_started()
async def bot_started(event: BotStarted):
    """Обработчик события запуска бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        RequestContactButton(text="📱 Поделиться контактом")
    )
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Здравствуйте! Чтобы получать уведомления и управлять своими визитами нажмите кнопку ниже, чтобы поделиться номером:',
        attachments=[builder.as_markup()]
    )

def get_button_menu():
    buttons = [[CallbackButton(text="МЕНЮ", payload=CallbackAction(action='menu').pack())]]
    payload = ButtonsPayload(buttons=buttons).pack()
    return payload
    
"""Загрузка всех визитов пациента"""
@dp.message_callback(CallbackAction.filter(F.action == 'visits'))
async def list_visits(event: MessageCallback, payload: CallbackAction):
    chat_id = getattr(event, 'chat_id', None) or (event.message.recipient.chat_id if hasattr(event.message, 'recipient') and event.message.recipient else None)
    
    if not chat_id:
        logging.error("Не удалось получить chat_id из события")
        return
    phone = await getPhone(chat_id)
    phone = hlp.validate_phone(phone)
    #phone = "79514469636"

    if not phone:
        await event.message.answer(text = "Номер телефона не найден. Пожалуйста, обновите контакт.")
        return
        
    async with RenovatioClient(MIS_API_URL, MIS_API_KEY, verify_ssl = False) as mis_client:
        patients = await mis_client.get_patient(mobile=phone)

        if not patients:
            await event.message.answer(text = "Пациентов по вашему номеру телефона не найдено, чтобы видеть визиты нужно в ЭМК указать этот номер телефона. Пожалуйста обратитесь в регистратуру любого центра Семейный доктор")
            return
            
        patients_id = []
        if isinstance(patients, list):
            for item in patients:
                patients_id.append(item['patient_id'])
            ids_str = ', '.join(map(str,patients_id))
        else:
            ids_str = str(patients['patient_id'])

        now = datetime.now()
        next_day = now + timedelta(days=60)
        formatted_date = next_day.strftime("%d.%m.%Y")

        appointments = await mis_client.get_appointments(
                patient_id = ids_str,   
                date_from = now.strftime("%d.%m.%Y")+" 00:00",
                date_to = formatted_date+" 23:59",
                status_id = "1,2,3"
            )

        if not appointments:
            await event.message.answer(text = "Предстоящих визитов не найдено")
            return

        await event.message.answer(text="Список ваших предстоящих визитов:")

        for item in appointments:

            appointment_id = str(item['id'])
            text = f"Дата: {item['time_start']} \nВрач: {item['doctor']} \nЦентр: {item['clinic']} "
            buttons = []

            if not item['confirm_status']:
                buttons.append([CallbackButton(text="Подтвердить визит", payload=ConfirmAppointment(appointment_id=appointment_id, action='confirm').pack())])
            else:
                text += "\n\nВизит подтверждён, ожидаем Вас в назначенное время"

            buttons.append([CallbackButton(text="ОТМЕНИТЬ", payload=ConfirmAppointment(appointment_id=appointment_id, action='cancel').pack(),intent = "negative")])

            payload = ButtonsPayload(buttons=buttons).pack()
            try:
                await event.bot.send_message(
                    chat_id=chat_id, 
                    text=text,
                    attachments=[payload]
                )
                logging.info(f"Визит отправлен в чат")
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")
                pass

"""Загрузка меню"""
@dp.message_callback(CallbackAction.filter(F.action == 'menu'))
async def get_menu(event: MessageCallback, payload: CallbackAction):
    buttons = [
        [CallbackButton(text="Мои визиты", payload=CallbackAction(action='visits').pack())],
        [LinkButton(text="Связаться с оператором колл-центра", url="https://max.ru/id7456020292_1_bot")],
        [RequestContactButton(text="Поделиться контактом")],
    ]
    payload = ButtonsPayload(buttons=buttons).pack()

    await event.message.answer(
        text="Пункты меню:",
        attachments=[payload]
    )


"""Подтверждение или отмена визита по его appointment_id"""
@dp.message_callback(ConfirmAppointment.filter((F.action == 'confirm') | (F.action == 'cancel')))
async def confirm_visit(event: MessageCallback, payload: ConfirmAppointment):
    action = payload.action
    appointment_id = payload.appointment_id
    
    chat_id = event.message.recipient.chat_id

    payload = get_button_menu()

    record = await collection.find_one({"chatId": chat_id})
    
    if not record:
        await event.message.answer(text = "Пожалуйста, поделитесь контактом, чтобы вы могли получать уведомления")
        return

    phone_number = (record.get("phoneNumber"))

    if not phone_number:
        await event.message.answer(text = "Номер телефона не найден. Пожалуйста, обновите контакт.", attachments=[payload])
        return

    async with RenovatioClient(MIS_API_URL, MIS_API_KEY, verify_ssl = False) as mis_client:
        appointments = await mis_client.get_appointments(appointment_id=appointment_id, show_patient_data=True,status_id = "1,2,3")
        #hlp.log_json(appointments)
        if not appointments:
            await event.message.answer(text = "Извините, визит уже отменен или не существует.", attachments=[payload])
            return

        appointment = appointments[0]
        phone_mis = hlp.validate_phone(appointment.get("patient_phone"))
        #phone_number = "79514469636"
        if phone_mis != phone_number:
            logging.error(f"Номер телефона не совпадает: {phone_number} vs {phone_mis}")
            await event.message.answer(text = "Визит или телефон не найден.", attachments=[payload])
            return

        if action == "confirm":
            res = await mis_client.confirm_appointment(appointment_id=appointment_id, source=7)
            msg = "Благодарим за подтверждение записи! Ожидаем Вас в назначенное время!"
        elif action == "cancel":
            res = await mis_client.cancel_appointment(appointment_id=appointment_id, source=7)
            msg = "Благодарим за то что нас уведомили, записывайтесь в удобное для Вас время!"
        
        if res:
            logging.info(f"Визит подтвержден: {appointment_id}")
        else:
            logging.error(f"Визит не подтвержден: {appointment_id}")
            msg = "Что-то пошло не так. Пожалуйста, свяжитесь с администратором."

        await event.message.answer(text=msg, attachments=[payload])



"""@dp.message_callback()
async def handle_callback(event: MessageCallback):
    #Обработчик нажатия inline-кнопок.
    # Логируем событие
    record = {
        "userId": event.from_user.user_id,
        "chatId": event.chat_id,
        "phoneNumber": getattr(event.from_user, 'phone_number', 'N/A'), # phone_number может быть недоступен
        "date": datetime.now(), # Исправлено: используем datetime.now() вместо устаревшего utcnow()
        "eventType": "callback_pressed",
        "callback_data": event.callback.payload
    }    
    await collection.insert_one(record)"""

@dp.message_created(ContactFilter())
async def on_contact(event, contact: Contact):
    user_id = event.from_user.user_id
    chat_id = event.message.recipient.chat_id
    full_name = contact.payload.vcf.full_name
    phone = contact.payload.vcf.phone
    clean_phone = hlp.validate_phone(phone)

    # Данные для обновления/вставки
    update_data = {
        "userId": user_id,
        "chatId": chat_id,
        "name": full_name,
        "date": datetime.now(),
        "eventType": "add_contact",
    }

    try:
        # 1. Ищем существующую запись по номеру телефона
        existing_record = await collection.find_one({"phoneNumber": clean_phone})

        if existing_record:
            # 2. Если запись есть, обновляем её
            # $set обновит указанные поля, остальные (например, старый eventType) останутся, 
            # но мы перезаписываем основные данные пользователя
            result = await collection.update_one(
                {"phoneNumber": clean_phone},
                {"$set": update_data}
            )
            logging.info(f"Запись для номера {clean_phone} обновлена. Изменено документов: {result.modified_count}")
        else:
            # 3. Если записи нет, создаем новую
            # Добавляем phoneNumber в данные для вставки, так как он был ключом поиска
            insert_data = update_data.copy()
            insert_data["phoneNumber"] = clean_phone
            
            result = await collection.insert_one(insert_data)
            logging.info(f"Новая запись в MongoDB добавлена с ID: {result.inserted_id}")

    except Exception as e:
        logging.error(f"Ошибка при работе с MongoDB (контакт): {e}")
    payloadbtn = get_button_menu()
    await event.message.answer(f"Ваш контакт добавлен! Теперь вы будете получать уведомления из центров Семейный доктор!", attachments=[payloadbtn])
    
@dp.message_created()
async def handle_message(event: MessageCreated):
    """ Обработчик всех входящих текстовых сообщений и других действий пользователя."""
    payload = get_button_menu()
    await event.message.answer(
        text="Извините, я не отвечаю на вопросы, а только присылаю уведомления. Для решения вашего вопроса, пожалуйста, воспользуйтесь меню по кнопке ниже",
        attachments=[payload]
    )


async def main():
    """Основная функция запуска бота."""
    await init_mongo()
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Получен сигнал остановки бота...")
    finally:
        # 1. Закрываем соединение с MongoDB
         if mongo_client:
             mongo_client.close()
         # 2. Закрываем сессию aiohttp внутри бота, если она существует
         # В зависимости от версии maxapi, сессия может быть доступна через bot.session
         if hasattr(bot, 'session') and bot.session:
             await bot.session.close()

         logging.info("Бот и ресурсы успешно остановлены.")         

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

