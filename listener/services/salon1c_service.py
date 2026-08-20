from datetime import date, datetime, timedelta
from libs.salon1c import SalonClient, SalonAPIError, make_sign, NotFoundError, TransportError
import logging
import asyncio
from aiocache import cached, Cache

CACHE_CONFIG_LONG = {"cache": Cache.MEMORY, "ttl": 3600*24*30}
CACHE_CONFIG = {"cache": Cache.MEMORY, "ttl": 3600*6}

RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0  # секунды между попытками


class SalonServiceError(Exception):
    """Ошибка сервиса 1С после исчерпания попыток"""
    pass


async def retry_on_failure(func, *args, max_attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, **kwargs):
    """
    Выполняет функцию с повторными попытками при ошибках 1С.
    
    Args:
        func: Асинхронная функция для вызова
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
                return await func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
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

    def _client(self) -> SalonClient:
        return SalonClient(api_key=self.api_key, salon_id=self.salon_id)
    
    @cached(**CACHE_CONFIG_LONG)
    async def get_book_services(self) -> list:
        services = self.client.bookings.book_services(self.salon_id)
        return services
    
    
    @cached(**CACHE_CONFIG_LONG)
    async def get_book_services_categories(self) -> list:
        categories = []
        seen_ids = set()  # для отслеживания уже добавленных id
        services = await self.get_book_services()
        
        for item in services:
            category = item.get("category")
            if category and category.get("id"):
                category_id = category["id"]
                if category_id not in seen_ids:  # проверка на дубликат
                    seen_ids.add(category_id)
                    categories.append({
                        'category_id': category_id,
                        'title': category["title"]
                    })
        return categories
    
    @cached(**CACHE_CONFIG_LONG)
    async def get_book_category_services(self, category_id:str) -> list:
        services = []
        services_all = await self.get_book_services()
        for item in services_all:
            category = item.get("category")
            if category and category.get("id"):
                if category["id"] == category_id:  
                    services.append(item)
        return services
    
    def get_history_client_visits(self, usertoken:str) -> list:
        list_visits = self.client.clients.records_history(self.salon_id, usertoken = usertoken)
        return list_visits
    
    def get_list_client_visits(self, usertoken:str) -> list:
        list_visits = self.client.clients.planned_records(self.salon_id, usertoken = usertoken)
        return list_visits
    
    @cached(**CACHE_CONFIG)
    async def get_staff_and_date(self, service_id:str,staff_id:str="") -> list:        
        start_date = date.today()
        end_date = date.today() + timedelta(days=14)
        
        try:
            staffs = await retry_on_failure(
                lambda: self.client.bookings.book_staff(self.salon_id, service_id = service_id)
            )
        except SalonServiceError as e:
            logging.error(f"Не удалось получить список мастеров: {e}")
            raise
        
        filtered_staffs = []
        for staff in staffs:

            if len(staff_id)>0 and staff_id != staff['id']:
                continue

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
            except SalonServiceError as e:
                logging.warning(f"Не удалось получить даты для мастера {staff['id']}: {e}")
                dates = []
            
            staff['available_dates'] = dates or []
            filtered_staffs.append(staff)
        return filtered_staffs
    
    @cached(**CACHE_CONFIG)
    async def get_time_staff(self, staff_id:str, service_id, select_date:str) -> list:
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

    @cached(**CACHE_CONFIG)
    def get_client(self, phone:str, usertoken:str) -> list:
        logging.info("get_client")
        #phone = "79026001548"
        #phone = "79525269602"
        #result = self.client.auth.auth(self.salon_id, login=phone)
        #data = self.client.auth.auth(self.salon_id, login=phone, confirmation_code=result['confirmation_code'])
        #logging.info(data)
        #userToken = "7257C0BFBA79BD01CACF168BB0CC4C35" #roma
        """
        result = self.client.auth.auth_request(self.salon_id, phone=phone,method="outgoing")
        logging.info(result)
        request_id = result['request_id']
        auth_token = self.client.auth.auth_token(self.salon_id, phone=phone,request_id=request_id,method="outgoing")
        logging.info(auth_token)
        """
        self.client.usertoken = usertoken
        user_client = self.client.clients.get_client(salon_id=self.salon_id, usertoken = usertoken)
        return user_client

    def auth_client(self, phone:str):
        #phone = "79026001548"
        result = self.client.auth.auth(self.salon_id, login=phone)
        data = self.client.auth.auth(self.salon_id, login=phone, confirmation_code=result['confirmation_code'])
        return data['UserToken'] or ""
    
    def validity_usertoken(self, usertoken:str):
        user_client = self.client.clients.get_client(salon_id=self.salon_id, usertoken = usertoken)
        if not user_client:
            return False
        return user_client
        #return self.client.auth.check_usertoken(self.salon_id, usertoken)


    def create_visit(self, usertoken:str, datetime_str:str, service_id:str, staff_id:str, comment:str=""):
        record_array = [
            {
                "datetime": datetime_str,
                "service_id": service_id,
                "staff_id": staff_id,
                "comment": comment
            }
        ]
        try:
            result = retry_on_failure(
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
    def cancel_visit(self, usertoken:str, record_id:str):
        try:
            result = retry_on_failure(
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