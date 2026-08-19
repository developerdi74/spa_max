"""Исключения SDK 1С:SPA-Салон."""

from __future__ import annotations

from typing import Any, Optional


class SalonError(Exception):
    """Базовое исключение SDK."""


class SalonAPIError(SalonError):
    """Ошибка, возвращённая API (структура Errors: {code, message})."""

    def __init__(self, code: Optional[int], message: str,
                 http_status: Optional[int] = None, raw: Any = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.raw = raw
        super().__init__(f"[{code}] {message} (HTTP {http_status})")


class AuthorizationError(SalonAPIError):
    """Ошибка авторизации (HTTP 401)."""

    def __init__(self, message: str = "Ошибка авторизации", raw: Any = None):
        super().__init__(code=None, message=message, http_status=401, raw=raw)


class BadRequestError(SalonAPIError):
    """Некорректный запрос (HTTP 400)."""


class InternalServerError(SalonAPIError):
    """Внутренняя ошибка сервера (HTTP 500)."""


class NotFoundError(SalonAPIError):
    """Объект не найден (HTTP 404)."""


class TransportError(SalonError):
    """Сетевая ошибка / таймаут."""


ERROR_MAP = {
    400: BadRequestError,
    401: AuthorizationError,
    404: NotFoundError,
    500: InternalServerError,
}


def raise_for_status(status_code: int, payload: Any) -> None:
    """Выбрасывает типизированное исключение по HTTP-статусу."""
    if 200 <= status_code < 300:
        return

    code, message = None, ""
    if isinstance(payload, dict):
        errors = payload.get("Errors") or payload.get("errors") or {}
        if isinstance(errors, dict):
            code = errors.get("code")
            message = errors.get("message") or ""
    elif isinstance(payload, str):
        message = payload

    exc_cls = ERROR_MAP.get(status_code, SalonAPIError)
    if exc_cls is AuthorizationError:
        raise AuthorizationError(message or "Ошибка авторизации", raw=payload)
    raise exc_cls(code=code, message=message or f"HTTP {status_code}",
                  http_status=status_code, raw=payload)