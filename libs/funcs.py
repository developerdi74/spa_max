import logging
import json
from datetime import datetime
import re

class HelperFunction:
    def validate_phone(phone):
        try:
            # Проверка на пустое значение
            if not phone:
                logging.warning("Пустой номер телефона")
                return None
            
            # Приводим к строке (на случай если пришел не str)
            phone = str(phone)
            
            # Очищаем номер от лишних символов
            clean_phone = re.sub(r'[^\d]', '', phone)
            
            # Проверяем, есть ли цифры в номере
            if not clean_phone:
                logging.warning(f"Нет цифр в номере: {phone}")
                return None
            
            # Нормализация номера
            if clean_phone.startswith('8') and len(clean_phone) == 11:
                clean_phone = '7' + clean_phone[1:]
            elif clean_phone.startswith('7') and len(clean_phone) == 11:
                pass
            elif clean_phone.startswith('9') and len(clean_phone) == 10:
                # Для номеров без кода страны (9XXXXXXXXX)
                clean_phone = '7' + clean_phone
            else:
                # Если номер не соответствует ожидаемому формату
                logging.warning(f"Некорректный формат номера: {phone} -> {clean_phone}")
                return None
            
            # Дополнительная валидация: проверяем, что номер состоит из 11 цифр
            if len(clean_phone) != 11:
                logging.warning(f"Некорректная длина номера: {clean_phone} ({len(clean_phone)} цифр)")
                return None
            
            #logging.info(f"Номер успешно валидирован: {clean_phone}")
            return clean_phone
            
        except Exception as e:
            logging.error(f"Ошибка валидации номера {phone}: {e}")
            return None
            
    def log_json(data, title=None):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s\n%(message)s')
        log = logging.getLogger(__name__)
        output = []
        if title:
            output.append(f"📌 {title}")
        output.append(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        log.info("\n".join(output))
            
    def formate_date(datastr):
        dt = datetime.strptime(datastr, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d.%m.%Y %H:%M')

    def shorten_name( full_name: str):
        parts = full_name.split()
        if len(parts) == 3:
            last_name, first_name, patronymic = parts
            return f"{last_name} {first_name[0]}.{patronymic[0]}."        
        if len(parts) == 2:
            last_name, first_name = parts
            return f"{last_name} {first_name[0]}."            
        return full_name