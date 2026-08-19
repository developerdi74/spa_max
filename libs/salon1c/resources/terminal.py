"""Терминал самообслуживания (API v2)."""

from __future__ import annotations

import json as _json
from typing import Any, List, Optional

from ..utils import clean_params, to_iso8601
from .base import BaseResource


class TerminalResource(BaseResource):

    def book_staff(self, datetime_=None) -> Any:
        """GET v2 book_staff — сотрудники для записи."""
        params = clean_params({
            "datetime": to_iso8601(datetime_) if datetime_ else None,
        })
        resp = self.http.get("/hs/api/v2/book_staff/", params=params)
        return self.data(resp)

    def book_services(self, staff_id: str) -> Any:
        """GET v2 book_services — услуги конкретного сотрудника."""
        resp = self.http.get("/hs/api/v2/book_services/",
                             params={"staff_id": staff_id})
        return self.data(resp)

    def find_client_by_phone(self, phone: str,usertoken) -> Any:
        """GET v2 find_client_by_phone — поиск клиента по телефону."""
        resp = self.http.get("/hs/api/v2/find_client_by_phone/",
                             params={"phone": phone},
                            usertoken=self.token(usertoken),)
        return resp
        return self.data(resp)

    def auth(
        self,
        phone: str,
        name: Optional[str] = None,
        birthday: Optional[str] = None,
        auth_type: Optional[str] = None,
    ) -> Any:
        """POST v2 auth — авторизация без подтверждения номера."""
        body = {"phone": phone}
        if name is not None:
            body["name"] = name
        if birthday is not None:
            body["birthday"] = birthday
        if auth_type is not None:
            body["auth_type"] = auth_type
            
        resp = self.http.post("/hs/api/v2/auth", json_body=body)
        return self.data(resp)

    def cart_cost(
        self,
        cart: List[dict],
        payment_list: Optional[List[dict]] = None,
        promocode: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET v2 cart_cost — стоимость корзины.

        cart: [{purchase_id, staff_id}, ...]
        """
        params = clean_params({
            "cart": _json.dumps(cart, ensure_ascii=False),
            "payment_list": _json.dumps(payment_list) if payment_list else None,
            "promocode": promocode,
        })
        resp = self.http.get(
            "/hs/api/v2/cart_cost/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def pay(
        self,
        transaction_id: str,
        receipt_number: str,
        cart: List[dict],
        payment_list: List[dict],
        promocode: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """POST v2 payment — оплата через терминал."""
        body = {
            "transaction_id": transaction_id,
            "receipt_number": receipt_number,
            "cart": cart,
            "payment_list": payment_list,
        }
        if promocode is not None:
            body["promocode"] = promocode
        resp = self.http.post(
            "/hs/api/v2/payment",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)