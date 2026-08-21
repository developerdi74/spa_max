from datetime import date, datetime, timedelta
from libs.salon1c import SalonClient, SalonAPIError, make_sign, NotFoundError, TransportError
import logging
import asyncio
from functools import wraps
from aiocache import cached, Cache
from typing import Any, Callable, TypeVar, Union
import aiohttp
from concurrent.futures import ThreadPoolExecutor

CACHE_CONFIG_LONG = {"cache": Cache.MEMORY, "ttl": 3600*24*30}
CACHE_CONFIG = {"cache": Cache.MEMORY, "ttl": 3600*6}

RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0  # секунды между попытками

# Пул потоков для блокирующих операций
_executor = ThreadPoolExecutor(max_workers=10)


class SalonServiceError(Exception):
    """Ошибка сервиса 1С после исчерпания попыток"""
    pass


T = TypeVar('T')


def run_sync_in_async(func: Callable[..., T], *args, **kwargs) -> asyncio.Future[T]:
    """Запускает синхронную функцию в executor для неблокирующего выполнения"""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, lambda: func(*args, **kwargs))


async def retry_on_failure(func: Callable, *args, max_attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, **kwargs):
    """
    Выполняет функцию с повторными попытками при ошибках 1С.
    
    Args:
        func: Функция для вызова (может быть sync или async)
        *args: Позиционные аргументы функции
        max_attempts: Максимальное количество попыток
        delay: Задержка между попытками (сек)
        **kwargs: Именованные аргументы функции
    
    Returns:
        Результат выполнения функции
    
    Raises:
        SalonServiceError: Если все попытки исчерпаны
    """
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await run_sync_in_async(func, *args, **kwargs)
            return result
        except (NotFoundError, TransportError, SalonAPIError) as e:
            last_exception = e
            logging.warning(
                f"Попытка {attempt}/{max_attempts} не удалась: {type(e).__name__}: {e}. "
                f"{'Повтор...' if attempt < max_attempts else ''}"
            )
            if attempt < max_attempts:
                await asyncio.sleep(delay * attempt)  # Экспоненциальная задержка
            continue
        except Exception as e:
            logging.error(f"Неожиданная ошибка: {type(e).__name__}: {e}")
            raise
    
    logging.error(f"Все {max_attempts} попыток исчерпаны. Последняя ошибка: {last_exception}")
    raise SalonServiceError(f"Сервис 1С недоступен после {max_attempts} попыток") from last_exception

class Salon1CService:
    def __init__(self, api_key: str, salon_id: str):
        self.api_key = api_key
        self.salon_id = salon_id
        self.client = self._client()
        self._token_cache: dict[str, tuple[str, datetime]] = {}  # Кэш токенов: phone -> (token, expiry)
        self._TOKEN_CACHE_TTL = 3600  # 1 час

    def _client(self) -> SalonClient:
        return SalonClient(api_key=self.api_key, salon_id=self.salon_id)
    
    @cached(**CACHE_CONFIG_LONG)
    async def get_book_services(self) -> list:
        """Получить список всех услуг салона (асинхронно)"""
        services = await run_sync_in_async(
            lambda: self.client.bookings.book_services(self.salon_id)
        )
        return services
    
    
    @cached(**CACHE_CONFIG_LONG)
    async def get_book_services_categories(self) -> list:
        """Получить список категорий услуг (асинхронно)"""
        categories = []
        seen_ids = set()
        services = await self.get_book_services()
        
        for item in services:
            category = item.get("category")
            if category and category.get("id"):
                category_id = category["id"]
                if category_id not in seen_ids:
                    seen_ids.add(category_id)
                    categories.append({
                        'category_id': category_id,
                        'title': category["title"]
                    })
        return categories
    
    @cached(**CACHE_CONFIG_LONG)
    async def get_book_category_services(self, category_id:str) -> list:
        """Получить услуги конкретной категории (асинхронно)"""
        services = []
        services_all = await self.get_book_services()
        for item in services_all:
            category = item.get("category")
            if category and category.get("id"):
                if category["id"] == category_id:  
                    services.append(item)
        return services
    
    async def get_history_client_visits(self, usertoken:str) -> list:
        """Получить историю визитов клиента (асинхронно)"""
        list_visits = await run_sync_in_async(
            lambda: self.client.clients.records_history(self.salon_id, usertoken=usertoken)
        )
        return list_visits
    
    async def get_list_client_visits(self, usertoken:str) -> list:
        """Получить запланированные визиты клиента (асинхронно)"""
        list_visits = await run_sync_in_async(
            lambda: self.client.clients.planned_records(self.salon_id, usertoken=usertoken)
        )
        return list_visits
    
    @cached(**CACHE_CONFIG)
    async def get_staff_and_date(self, service_id:str,staff_id:str="") -> list:        
        """Получить список мастеров и доступные даты (асинхронно, параллельно)"""
        start_date = date.today()
        end_date = date.today() + timedelta(days=14)
        
        try:
            staffs = await retry_on_failure(
                lambda: self.client.bookings.book_staff(self.salon_id, service_id=service_id)
            )
        except SalonServiceError as e:
            logging.error(f"Не удалось получить список мастеров: {e}")
            raise
        
        filtered_staffs = []
        
        # Параллельный запрос дат для всех мастеров через asyncio.gather
        async def fetch_dates_for_staff(staff):
            if len(staff_id) > 0 and staff_id != staff['id']:
                return None
            
            try:
                dates = await retry_on_failure(
                    lambda s=staff: self.client.bookings.book_dates(
                        self.salon_id,
                        start_date=start_date,
                        end_date=end_date,
                        service_id=service_id,
                        staff_id=s['id']
                    )
                )
                return {**staff, 'available_dates': dates or []}
            except SalonServiceError as e:
                logging.warning(f"Не удалось получить даты для мастера {staff['id']}: {e}")
                return {**staff, 'available_dates': []}
        
        # Запускаем все запросы параллельно
        tasks = [fetch_dates_for_staff(staff) for staff in staffs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Фильтруем результаты
        for result in results:
            if isinstance(result, Exception):
                logging.error(f"Ошибка при получении дат: {result}")
                continue
            if result is not None:
                filtered_staffs.append(result)
        
        return filtered_staffs
    
    @cached(**CACHE_CONFIG)
    async def get_time_staff(self, staff_id:str, service_id, select_date:str) -> list:
        """Получить свободное время для мастера на дату (асинхронно)"""
        datetime_ = datetime.strptime(select_date, "%d.%m.%Y")
        try:
            time_list = await retry_on_failure(
                lambda: self.client.bookings.book_times(
                    self.salon_id,
                    datetime_=datetime_,
                    service_id=service_id,
                    staff_id=staff_id
                )
            )
        except SalonServiceError as e:
            logging.error(f"Не удалось получить время для мастера {staff_id}: {e}")
            raise
        return time_list or []

    async def get_client(self, phone:str, usertoken:str) -> list:
        """Получить данные клиента (асинхронно)"""
        logging.info("get_client")
        self.client.usertoken = usertoken
        user_client = await run_sync_in_async(
            lambda: self.client.clients.get_client(salon_id=self.salon_id, usertoken=usertoken)
        )
        return user_client

    async def auth_client(self, phone:str) -> str:
        """Авторизация клиента по телефону (асинхронно) с кэшированием токена"""
        # Проверяем кэш
        now = datetime.now()
        if phone in self._token_cache:
            token, expiry = self._token_cache[phone]
            if now < expiry:
                logging.info(f"Используем закэшированный токен для {phone}")
                return token
        
        # Токена нет в кэше или он истёк - запрашиваем новый
        logging.info(f"Запрашиваем новый токен для {phone}")
        try:
            result = await run_sync_in_async(
                lambda: self.client.auth.auth(self.salon_id, login=phone)
            )
            data = await run_sync_in_async(
                lambda: self.client.auth.auth(
                    self.salon_id, 
                    login=phone, 
                    confirmation_code=result['confirmation_code']
                )
            )
            token = data.get('UserToken', '')
            
            # Кэшируем токен
            if token:
                self._token_cache[phone] = (token, now + timedelta(seconds=self._TOKEN_CACHE_TTL))
                logging.info(f"Токен для {phone} закэширован на {self._TOKEN_CACHE_TTL} сек")
            
            return token
        except Exception as e:
            logging.error(f"Ошибка авторизации клиента {phone}: {e}")
            return ""
    
    async def validity_usertoken(self, usertoken:str) -> bool | dict:
        """Проверка валидности usertoken (асинхронно)"""
        try:
            user_client = await run_sync_in_async(
                lambda: self.client.clients.get_client(salon_id=self.salon_id, usertoken=usertoken)
            )
            if not user_client:
                return False
            return user_client
        except Exception as e:
            logging.warning(f"Ошибка проверки токена: {e}")
            return False


    async def create_visit(self, usertoken:str, datetime_str:str, service_id:str, staff_id:str, comment:str=""):
        """Создать визит клиента (асинхронно)"""
        record_array = [
            {
                "datetime": datetime_str,
                "service_id": service_id,
                "staff_id": staff_id,
                "comment": comment
            }
        ]
        try:
            result = await retry_on_failure(
                lambda: self.client.bookings.book_record(
                    salon_id=self.salon_id,
                    usertoken=usertoken,
                    record_array=record_array
                )
            )
            return result
        except SalonServiceError as e:
            logging.error(f"Не удалось создать визит: {e}")
            raise
    
    async def cancel_visit(self, usertoken:str, record_id:str):
        """Отменить визит клиента (асинхронно)"""
        try:
            result = await retry_on_failure(
                lambda: self.client.bookings.cancel_record(
                    salon_id=self.salon_id,
                    usertoken=usertoken,
                    record_id=record_id
                )
            )
            return result
        except SalonServiceError as e:
            logging.error(f"Не удалось отменить визит: {e}")
            raise
