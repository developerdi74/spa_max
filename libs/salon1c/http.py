"""HTTP-транспорт: сессия, авторизация, запросы, парсинг ошибок."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    Retry = None

from .exceptions import TransportError, raise_for_status

DEFAULT_BASE_URL = "http://cloud.salon1c.ru/api/"


class HTTPClient:
    """Низкоуровневый HTTP-клиент с поддержкой basicAuth / apiKey."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        basic_auth: Optional[tuple] = None,
        timeout: float = 30.0,
        max_retries: int = 0,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.timeout = timeout
        self.session = session or requests.Session()

        if api_key:
            self.session.headers["apikey"] = api_key
        if basic_auth:
            self.session.auth = basic_auth

        if max_retries and Retry is not None:
            retry = Retry(
                total=max_retries,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET", "POST", "PUT", "DELETE"),
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

    # ------------------------------------------------------------------ #
    def build_url(self, path: str) -> str:
        path = path.lstrip("/")
        return urljoin(self.base_url, path)

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        usertoken: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        raw_response: bool = False,
    ) -> Any:
        url = self.build_url(path)
        req_headers = dict(headers or {})
        if usertoken:
            req_headers["usertoken"] = usertoken

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json_body,
                headers=req_headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"Сетевая ошибка: {exc}") from exc

        if raw_response:
            # Для public_offer / privacy_policy возвращаем текст
            raise_for_status(response.status_code, response.text)
            return response.text

        payload = self._parse_json(response)
        raise_for_status(response.status_code, payload)
        return payload

    @staticmethod
    def _parse_json(response: requests.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    # Удобные обёртки -------------------------------------------------- #
    def get(self, path, **kw):    return self.request("GET", path, **kw)
    def post(self, path, **kw):   return self.request("POST", path, **kw)
    def put(self, path, **kw):    return self.request("PUT", path, **kw)
    def delete(self, path, **kw): return self.request("DELETE", path, **kw)

    def close(self) -> None:
        self.session.close()