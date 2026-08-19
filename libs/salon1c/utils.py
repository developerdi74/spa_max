"""Вспомогательные функции (подпись SHA1, форматирование дат и т.д.)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Sequence

# Порядок полей для формирования цифровой подписи (private_auth)
_SIGN_FIELDS = ("birthday", "email", "last_name", "name",
                "phone", "second_name", "sex")


def make_sign(data: Dict[str, Any]) -> str:
    """Формирует цифровую подпись SHA1 для метода private_auth.

    Строка собирается как пары ``ключ;значение`` для полей:
    birthday, email, last_name, name, phone, second_name, sex.
    Пустое значение -> только ключ без значения (``birthday;``).

    Пример:
        birthday;31.12.1990;email;test@mail.ru;last_name;Иванов;
        name;Иван;phone;79876543210;second_name;Иванович;sex;1
    """
    parts = []
    for field in _SIGN_FIELDS:
        value = data.get(field)
        value = "" if value is None else str(value)
        parts.append(f"{field};{value}")
    raw = ";".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def to_iso8601(value: Any) -> str:
    """Преобразует дату/datetime в формат API iso8601 (20170820T0000)."""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.strftime("%Y%m%dT%H%M")
    if isinstance(value, date):
        return value.strftime("%Y%m%dT0000")
    raise TypeError(f"Не удалось преобразовать в iso8601: {value!r}")


def services_array_json(service_ids: Sequence[str]) -> str:
    """JSON-строка с массивом ID услуг (параметр service_ids).

    Формат: {"services_array": ["id1", "id2"]}
    """
    return json.dumps({"services_array": list(service_ids)},
                      ensure_ascii=False)


def clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет из словаря query-параметров все None."""
    return {k: v for k, v in params.items() if v is not None}


def to_bool_str(value: Optional[bool]) -> Optional[str]:
    """Преобразует bool в строку для query-параметров."""
    if value is None:
        return None
    return "true" if value else "false"