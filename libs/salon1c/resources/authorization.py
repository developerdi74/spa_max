"""Авторизация клиентов."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..utils import make_sign
from .base import BaseResource


class AuthorizationResource(BaseResource):

    def get_auth_types(self, salon_id: str) -> Any:
        """GET auth_types — доступные варианты авторизации."""
        resp = self.http.get(f"/hs/api/v1/auth_types/{salon_id}/")
        return self.data(resp)

    def auth(
        self,
        salon_id: str,
        login: str,
        confirmation_code: Optional[str] = None,
        name: Optional[str] = None,
        last_name: Optional[str] = None,
        second_name: Optional[str] = None,
        birthday: Optional[str] = None,
        email: Optional[str] = None,
        auth_type: Optional[str] = None,
    ) -> Any:
        """POST auth — авторизация по SMS / иному методу.

        Без confirmation_code отправляет новый код (вернёт sent_SMS).
        С кодом — возвращает UserToken.
        """
        body = {"login": login}
        for key, value in {
            "confirmation_code": confirmation_code,
            "name": name, "last_name": last_name,
            "second_name": second_name, "birthday": birthday,
            "email": email, "auth_type": auth_type,
        }.items():
            if value is not None:
                body[key] = value
        resp = self.http.post(f"/hs/api/v1/auth/{salon_id}/", json_body=body)
        return self.data(resp)

    def check_usertoken(self, usertoken: str, salon_id: str = "any") -> bool:
        """POST validity_usertoken — проверка валидности ключа."""
        resp = self.http.post(f"/hs/api/v1/validity_usertoken/{salon_id}/",
                              usertoken=usertoken)
        if isinstance(resp, dict):
            return bool(resp.get("Result"))
        return False

    def private_auth(
        self,
        salon_id: str,
        phone: str,
        name: Optional[str] = None,
        last_name: Optional[str] = None,
        second_name: Optional[str] = None,
        birthday: Optional[str] = None,
        email: Optional[str] = None,
        sex: Optional[str] = None,
        sign: Optional[str] = None,
    ) -> Any:
        """POST private_auth — авторизация по цифровой подписи SHA1.

        Если sign не передан, подпись рассчитывается автоматически.
        """
        data = {
            "phone": phone, "name": name, "last_name": last_name,
            "second_name": second_name, "birthday": birthday,
            "email": email, "sex": sex,
        }
        if sign is None:
            sign = make_sign(data)

        body = {k: v for k, v in data.items() if v is not None}
        body["sign"] = sign
        resp = self.http.post(f"/hs/api/v1/private_auth/{salon_id}/",
                              json_body=body)
        return self.data(resp)

    def auth_request(
        self,
        salon_id: str,
        phone: str,
        method: str,
        request_id: Optional[str] = None,
        name: Optional[str] = None,
        last_name: Optional[str] = None,
        second_name: Optional[str] = None,
        birthday: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Any:
        """POST auth_request — исходящее подтверждение номера телефона."""
        body = {"phone": phone, "method": method}
        for key, value in {
            "request_id": request_id, "name": name, "last_name": last_name,
            "second_name": second_name, "birthday": birthday, "email": email,
        }.items():
            if value is not None:
                body[key] = value
        resp = self.http.post(f"/hs/api/v1/auth_request/{salon_id}",
                              json_body=body)
        return self.data(resp)

    def auth_token(
        self,
        salon_id: str,
        request_id: str,
        phone: Optional[str] = None,
        method: Optional[str] = None,
    ) -> Any:
        """POST auth_token — получение UserToken после подтверждения."""
        body = {"request_id": request_id}
        if phone is not None:
            body["phone"] = phone
        if method is not None:
            body["method"] = method
        resp = self.http.post(f"/hs/api/v1/auth_token/{salon_id}",
                              json_body=body)
        return resp
        return self.data(resp)