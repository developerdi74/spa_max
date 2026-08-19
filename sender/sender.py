"""
Сервис для рассылки уведомлений из Renovation в МАКС в установленное время в .env NOTIFICATION_TIME
Путь: /maxprojects/sender/sender.py
Библиотеки: 
    /maxprojects/libs/funcs.py
    /maxprojects/libs/renovation_api.py
"""
import asyncio
import logging

import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from libs.renovation_api import RenovatioClient 
from libs.funcs import HelperFunction as hlp
from maxapi.filters.callback_payload import CallbackPayload
from datetime import datetime,timedelta
import aiohttp
import os
from motor.motor_asyncio import AsyncIOMotorClient
from maxapi import Bot, Dispatcher, F
from dotenv import load_dotenv, find_dotenv
import atexit
from maxapi.enums.format import Format
from maxapi.utils.formatting import (Blockquote,Bold,Heading,Italic,Link,as_html,)
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import (ClipboardButton,LinkButton,CallbackButton)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

# КОНФИГУРАЦИЯ
MONGO_URI = os.getenv("MONGO_URI") # Адрес вашего сервера с MongoDB
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")

# Данные для МИС Renovatio
MIS_API_URL = os.getenv("MIS_API_URL")
MIS_API_KEY = os.getenv("MIS_API_KEY")
DAYS_BEFORE = int(os.getenv("DAYS_BEFORE", 20))

class ConfirmAppointment(CallbackPayload, prefix='confirmAppointment'):
    appointment_id: str
    action: str

class CallbackAction(CallbackPayload, prefix='visits'):
    action: str

class NotificationSender:
    def __init__(self, mongo_uri, db_name, collection_name, bot_token):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.bot = Bot(token=bot_token)
        self.mis_client = RenovatioClient(MIS_API_URL, MIS_API_KEY,verify_ssl = False)

    async def send_notification(self, chat_id, text):
        """Отправка сообщения пользователю через MAX API"""
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Сообщение отправлено пользователю {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")
            return False    

    async def send_confirmation(self, chat_id, text, appointment_id):
        #отправка кнопок подтверждения или отмены визита
        buttons = [
            [CallbackButton(text="Подтвердить визит", payload=ConfirmAppointment(appointment_id=appointment_id, action='confirm').pack())],
            #[CallbackButton(text="ОТМЕНИТЬ ВИЗИТ(по клику визит будет отменён)", payload=ConfirmAppointment(appointment_id=appointment_id, action='cancel').pack(),intent = "negative")]
            [CallbackButton(text="МЕНЮ", payload=CallbackAction(action='menu').pack())],
        ]
        payload = ButtonsPayload(buttons=buttons).pack()

        try:
            await self.bot.send_message(
                chat_id=chat_id, 
                text=text,
                attachments=[payload],
                format=Format.HTML
            )
            logger.info(f"Подтверждение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            #logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")
            return False

    async def process_notifications(self):
        """Основная логика: получить данные из МИС -> найти в Mongo -> отправить"""
        logger.info("Запуск процесса рассылки...")
        
        # 1. Получаем данные из МИС
        #patients = await self.mis_client.get_patients_with_appointments()

        now = datetime.now()
        next_day = now + timedelta(days=DAYS_BEFORE)
        formatted_date = next_day.strftime("%d.%m.%Y")

        appointments=[]
        logging.info(formatted_date)
        appointments = await self.mis_client.get_appointments(
            date_from = formatted_date+" 00:00",
            date_to = formatted_date+" 23:59",
            status_id = '1,2,3'
        );

        countVisits = len(appointments)
        logging.info(countVisits)
        sent_count = 0
        #для тестов
        """appointments = [
            {
                "id": "100994",
                "clinic": "Доменщиков 8а",
                "patient_phone": "+7 (991) 898-17-29",
                "time_start": "28.04.2026 07:30",
                "room": "23",
                "doctor": "Капельницы Д.",
            },
            {
               "id": "100994",
               "clinic": "Доменщиков 8а",
               "patient_phone": "79193422046",
               "time_start": "28.04.2026 07:30",
               "room": "23",
               "doctor": "Капельницы Д."
            },
        ]"""
        for item in appointments:
            if item['confirm_status']:
                continue

            clean_phone = hlp.validate_phone(item['patient_phone'])
            phone = clean_phone
            if not phone:
                continue

            user_record = await self.collection.find_one({"phoneNumber": clean_phone})

            if not user_record:
                 # Альтернативный поиск, если форматы телефонов отличаются
                 user_record = await self.collection.find_one({"phoneNumber": {"$regex": clean_phone[-10:]}})

            if user_record:
                #hlp.log_json(item);
                chat_id = user_record.get('chatId')
                apid = str(item['id'])
                if chat_id:
                    message_text = as_html(
                        Heading(f"Здравствуйте! Подтверждение Вашего визита!"),
                        "\n",
                        "\n",
                        Bold(item['time_start']),
                        f" у Вас запланирован визит",
                        f" в ",Bold('МЦ Семейный доктор')," по адресу: \n",Bold(item['clinic']),
                        "\n",
                        f"Врач: {item.get('doctor')}","\n",
                        f"Кабинет: { 'уточните у администратора' if item.get('room') else item.get('room')}",
                        "\n",
                        "Пожалуйста, не забудьте с собой паспорт, СНИЛС(для больничного), ребенку свидетельство о рождении.",
                        "\n",
                        "\n",
                        Bold("Для подтверждения визита нажмите, пожалуйста, на кнопку ниже."),
                        "\n",
                        "\n",
                        Link("Памятки для подготовки", url="https://mgn-doctor.ru/documents/memos/"),
                    )
                    success = await self.send_confirmation(chat_id, message_text, appointment_id = apid)
                    if success:
                        sent_count += 1
                        await asyncio.sleep(0.5)
            else:
                logger.debug(f"Пользователь с телефоном {phone} не найден в базе бота.")
                pass

        if not appointments:
            logger.info("Пациенты не найдены или ошибка API.")
            return

        logger.info(f"Получено {countVisits} записей из МИС.")
        logger.info(f"Рассылка завершена. Отправлено сообщений: {sent_count}")

    async def close(self):
        """Корректное закрытие соединений"""
        
        # 1. Закрываем сессию бота (maxapi)
        if self.bot:
            try:
                if hasattr(self.bot, 'close_session'):
                    await self.bot.close_session()
                    logger.info("Сессия бота закрыта через close_session()")
                elif hasattr(self.bot, 'session') and self.bot.session:
                    if not self.bot.session.closed:
                        await self.bot.session.close()
                        logger.info("Сессия бота закрыта через .session.close()")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии сессии бота: {e}")
        
        # 2. Закрываем сессию клиента МИС (RenovatioClient)
        if self.mis_client:
            try:
                # Попытка закрыть через стандартный метод close/aclose, если он есть
                if hasattr(self.mis_client, 'close'):
                    await self.mis_client.close()
                    logger.info("Сессия МИС закрыта через close()")
                elif hasattr(self.mis_client, 'aclose'):
                    await self.mis_client.aclose()
                    logger.info("Сессия МИС закрыта через aclose()")
                # Попытка закрыть прямую сессию aiohttp, если она доступна
                elif hasattr(self.mis_client, 'session') and self.mis_client.session:
                    if not self.mis_client.session.closed:
                        await self.mis_client.session.close()
                        logger.info("Сессия МИС закрыта через .session.close()")
                else:
                    logger.warning("Не удалось найти метод закрытия сессии для RenovatioClient")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии сессии МИС: {e}")

        # 3. Закрываем клиент MongoDB
        if self.client:
            self.client.close()
            logger.info("Клиент MongoDB закрыт")

async def main2():
    sender = NotificationSender(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        collection_name=COLLECTION_NAME,
        bot_token=MAX_BOT_TOKEN
    )    
    try:
        await sender.process_notifications()
    finally:
        await sender.close()

async def main():
    sender = NotificationSender(
        mongo_uri=MONGO_URI,
        db_name=DB_NAME,
        collection_name=COLLECTION_NAME,
        bot_token=MAX_BOT_TOKEN
    )

    scheduler = AsyncIOScheduler()

    # Список переменных времени из .env
    time_vars = {
        "NOTIFICATION_TIME": os.getenv("NOTIFICATION_TIME", "9:00"),
        "NOTIFICATION_TIME_TWO": os.getenv("NOTIFICATION_TIME_TWO", "12:00")
    }

    for var_name, time_str in time_vars.items():
        if not time_str:
            continue
        try:
            hour, minute = map(int, time_str.split(':'))
            scheduler.add_job(
                sender.process_notifications,
                trigger='cron',
                hour=hour,
                minute=minute,
                id=f'job_{var_name.lower()}',
                name=f'Рассылка ({time_str})'
            )
            logger.info(f"✅ Задача добавлена на {time_str}")
        except ValueError:
            logger.error(f"❌ Неверный формат времени для {var_name}: {time_str}")

    scheduler.start()
    #logger.info("🚀 Планировщик запущен. Ожидание сигнала остановки...")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("🛑 Получен сигнал остановки. Завершение работы...")
    finally:
        scheduler.shutdown()
        await sender.close()
        logger.info("🔌 Ресурсы закрыты.")

if __name__ == '__main__':
    #Одиночный запуск
    #asyncio.run(main())
    
    #ДЛЯ РЕГУЛЯРНОЙ РАБОТЫ (раскомментируйте блок ниже)
    logger.info(f"Текущее время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass # Игнорируем повторный KeyboardInterrupt на верхнем уровне