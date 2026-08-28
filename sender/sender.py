"""
Сервис для рассылки подтверждений визитов клиентов в установленное время из .env NOTIFICATION_TIME
Путь: /workspace/sender/sender.py
Библиотеки: 
    /workspace/libs/funcs.py
    /workspace/libs/salon1c/client.py
    /workspace/listener/services/salon1c_service.py
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

import aiohttp
import os
from motor.motor_asyncio import AsyncIOMotorClient
from maxapi import Bot, Dispatcher, F
from dotenv import load_dotenv, find_dotenv
from maxapi.enums.format import Format
from maxapi.utils.formatting import Blockquote, Bold, Heading, Italic, Link, as_html
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import ClipboardButton, LinkButton, CallbackButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from libs.funcs import HelperFunction as hlp
from libs.salon1c import SalonClient, SalonAPIError, make_sign, NotFoundError, TransportError
from listener.services.salon1c_service import Salon1CService
from listener.payloads import ConfirmAppointmentPayload, CallbackAction

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

# КОНФИГУРАЦИЯ
MONGO_URI = os.getenv("MONGO_URI")  # Адрес вашего сервера с MongoDB
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")

# Данные для МИС Renovatio
SALON_ID = os.getenv("SALON_ID", "")
API_KEY = os.getenv("API_KEY", "")
DAYS_BEFORE = int(os.getenv("DAYS_BEFORE", 20))


class NotificationSender:
    def __init__(self, mongo_uri, db_name, collection_name, bot_token):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.bot = Bot(token=bot_token)
        self.salon1c_service = Salon1CService(api_key=API_KEY, salon_id=SALON_ID)

    async def send_notification(self, chat_id, text):
        """Отправка сообщения пользователю через MAX API"""
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Сообщение отправлено пользователю {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")
            return False    

    async def send_confirmation(self, chat_id: int, text: str, appointment_id: str) -> bool:
        """Отправка кнопок подтверждения или отмены визита"""
        buttons = [
            [CallbackButton(text="Подтвердить визит", payload=ConfirmAppointmentPayload(appointment_id=appointment_id, action='confirmation').pack())],
            #[CallbackButton(text="ОТМЕНИТЬ ВИЗИТ(по клику визит будет отменён)", payload=ConfirmAppointment(appointment_id=appointment_id, action='cancel').pack(),intent = "negative")],
            [CallbackButton(text="Основное меню", payload=CallbackAction(action='menu').pack())],
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
            logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")
            return False

    async def process_notifications(self) -> None:
        """Основная логика: получить данные из МИС -> найти в Mongo -> отправить"""
        formatted_date = datetime.now().strftime("%d.%m.%Y")
        logger.info(f"Запуск процесса рассылки... {formatted_date}")
        
        appointments = await self.salon1c_service.get_visites()
        count_visits = len(appointments)
        sent_count = 0
        
        for item in appointments:
            #hlp.log_json(item)
            status = item.get("status", [])

            client = item.get("client", {})
            if not client:
                continue
            
            phones = client.get("phones", [])
            if not phones:
                continue

            phone = phones[0]
            clean_phone = hlp.validate_phone(phone)
            
            if not clean_phone:
                continue

            if status != "Expected":
                continue
            
            #clean_phone = "79918981729" 

            user_record = await self.collection.find_one({"phoneNumber": clean_phone})

            if not user_record:
                # Альтернативный поиск, если форматы телефонов отличаются
                user_record = await self.collection.find_one({"phoneNumber": {"$regex": clean_phone[-10:]}})

            if user_record:
                hlp.log_json(item)
                chat_id = user_record.get('chatId')
                if chat_id:
                    apid = str(item['id'])
                    services = item["services"]
                    if not services:
                        continue
                    
                    srv = services[0]
                    start_date = srv.get("start_date")
                    if not start_date:
                        continue
                    
                    dt = datetime.fromisoformat(start_date)
                    format_date = dt.strftime("%d.%m.%Y %H:%M")
                    
                    service = srv.get("service", {})
                    service_title = service.get("title", "")
                    
                    staff = srv.get("staff", {})
                    staff_title = staff.get("title", "")
                    
                    message_text = as_html(
                        Heading("Здравствуйте! \nПожалуйста, подтвердите запись в центр красоты и здоровья «Другое измерение»"),
                        "\n",
                        "\n",
                        f"📅 " + Bold(format_date) + " у Вас запланирован визит по адресу:",
                        f"\n📍 "+Bold('пр. Ленина, 27'),
                        "\n",
                        "\n",
                        f"👤 Специалист: {staff_title}",
                        f"\n💆‍♀️ Услуга: {service_title}",
                        "\n",
                        "\n",
                        Bold("Пожалуйста, подтвердите Ваш визит, нажав на кнопку ниже."),
                        "\n",
                        "\n",
                        "С уважением,",
                        "Центр красоты и здоровья «Другое измерение»"
                    )
                    success = await self.send_confirmation(chat_id, message_text, appointment_id=apid)
                    if success:
                        sent_count += 1
                        await asyncio.sleep(0.5)
            else:
                logger.debug(f"Пользователь с телефоном {phone} не найден в базе бота.")

        if not appointments:
            logger.info("Пациенты не найдены или ошибка API.")
            return

        logger.info(f"Получено {count_visits} записей из МИС.")
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
        if self.salon1c_service:
            try:
                # Попытка закрыть через стандартный метод close/aclose, если он есть
                if hasattr(self.salon1c_service, 'close'):
                    await self.salon1c_service.close()
                    logger.info("Сессия МИС закрыта через close()")
                elif hasattr(self.salon1c_service, 'aclose'):
                    await self.salon1c_service.aclose()
                    logger.info("Сессия МИС закрыта через aclose()")
                # Попытка закрыть прямую сессию aiohttp, если она доступна
                elif hasattr(self.salon1c_service, 'session') and self.salon1c_service.session:
                    if not self.salon1c_service.session.closed:
                        await self.salon1c_service.session.close()
                        logger.info("Сессия МИС закрыта через .session.close()")
                else:
                    logger.warning("Не удалось найти метод закрытия сессии для RenovatioClient")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии сессии МИС: {e}")

        # 3. Закрываем клиент MongoDB
        if self.client:
            self.client.close()
            logger.info("Клиент MongoDB закрыт")

async def main2() -> None:
    """Одиночный запуск процесса рассылки"""
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

async def main() -> None:
    """Запуск планировщика для регулярной работы"""
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
    logger.info("🚀 Планировщик запущен. Ожидание сигнала остановки...")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("🛑 Получен сигнал остановки. Завершение работы...")
    finally:
        scheduler.shutdown()
        await sender.close()
        logger.info("🔌 Ресурсы закрыты.")

if __name__ == '__main__':
    # ДЛЯ РЕГУЛЯРНОЙ РАБОТЫ (раскомментируйте блок ниже)
    # Одиночный запуск (закомментировать для production)
    # asyncio.run(main2())
    
    logger.info(f"Текущее время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Игнорируем повторный KeyboardInterrupt на верхнем уровне