"""Базовый класс для всех ресурсов."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..client import SalonClient


class BaseResource:
    def __init__(self, client: "SalonClient"):
        self._client = client

    # Доступ к HTTP-слою и токену по умолчанию ------------------------ #
    @property
    def http(self):
        return self._client.http

    def token(self, usertoken: Optional[str]) -> Optional[str]:
        return usertoken or self._client.usertoken

    @staticmethod
    def data(payload: Any) -> Any:
        """Извлекает полезные данные (Parameters/parameters) из ответа."""
        if isinstance(payload, dict):
            if "Parameters" in payload:
                return payload["Parameters"]
            if "parameters" in payload:
                return payload["parameters"]
        return payload