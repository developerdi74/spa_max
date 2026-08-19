"""Онлайн-магазин."""

from __future__ import annotations

import json as _json
from typing import Any, List, Optional

from ..utils import clean_params, to_iso8601
from .base import BaseResource


class OnlineStoreResource(BaseResource):

    def price_list(
        self,
        salon_id: str,
        type: Optional[str] = None,
        product_id: Optional[List[str]] = None,
        group_id: Optional[str] = None,
        page_count: Optional[int] = None,
        page_number: Optional[int] = None,
        search_line: Optional[str] = None,
        without_remainder: Optional[bool] = None,
        with_group: Optional[bool] = None,
        filters: Optional[List[dict]] = None,
        code: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET price_list — прайс-лист номенклатуры."""
        params = clean_params({
            "type": type,
            "product_id": _json.dumps(product_id) if product_id else None,
            "group_id": group_id,
            "page_count": page_count,
            "page_number": page_number,
            "search_line": search_line,
            "without_remainder": without_remainder,
            "with_group": with_group,
            "filters": _json.dumps(filters) if filters else None,
            "code": code,
        })
        resp = self.http.get(
            f"/hs/api/v1/price_list/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def cart_cost(
        self,
        salon_id: str,
        cart: List[dict],
        delivery: Optional[dict] = None,
        cart_pay: Optional[dict] = None,
        client: Optional[dict] = None,
        promocode: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET cart_cost — стоимость корзины.

        cart: [{purchase_id, count}, ...]
        """
        params = clean_params({
            "cart": _json.dumps(cart, ensure_ascii=False),
            "delivery": _json.dumps(delivery) if delivery else None,
            "cart_pay": _json.dumps(cart_pay) if cart_pay else None,
            "client": _json.dumps(client) if client else None,
            "promocode": promocode,
        })
        resp = self.http.get(
            f"/hs/api/v1/cart_cost/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def pay(
        self,
        salon_id: str,
        transaction_id: str,
        cart: List[dict],
        payment_list: List[dict],
        gift_to: Optional[dict] = None,
        comment: Optional[str] = None,
        address: Optional[str] = None,
        delivery: Optional[dict] = None,
        promocode: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """POST payment — оплата заказа."""
        body = {
            "transaction_id": transaction_id,
            "cart": cart,
            "payment_list": payment_list,
        }
        for key, value in {
            "gift_to": gift_to, "comment": comment, "address": address,
            "delivery": delivery, "promocode": promocode,
        }.items():
            if value is not None:
                body[key] = value
        resp = self.http.post(
            f"/hs/api/v1/payment/{salon_id}",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def cancel_payment(
        self,
        salon_id: str,
        order_id: str,
        row_id: str,
        usertoken: Optional[str] = None,
    ) -> Any:
        """DELETE payment — отмена оплаты."""
        resp = self.http.delete(
            f"/hs/api/v1/payment/{salon_id}",
            params={"order_id": order_id, "row_id": row_id},
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def group_list(self, salon_id: str) -> Any:
        """GET group_list — разделы товаров (иерархия)."""
        resp = self.http.get(f"/hs/api/v1/group_list/{salon_id}")
        return self.data(resp)

    def contact_information(self, salon_id: str) -> Any:
        """GET contact_information — контакты магазина."""
        resp = self.http.get(f"/hs/api/v1/contact_information/{salon_id}")
        return self.data(resp)

    def public_offer(self, salon_id: str) -> str:
        """GET public_offer — HTML публичной оферты."""
        return self.http.get(f"/hs/api/v1/public_offer/{salon_id}",
                             raw_response=True)

    def privacy_policy(self, salon_id: str) -> str:
        """GET privacy_policy — HTML политики конфиденциальности."""
        return self.http.get(f"/hs/api/v1/privacy_policy/{salon_id}",
                             raw_response=True)

    def order_list(
        self,
        salon_id: str,
        start_date=None,
        end_date=None,
        page_count: Optional[int] = None,
        page_number: Optional[int] = None,
        status: Optional[str] = None,
        order_number: Optional[str] = None,
        order_id: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET order_list — история заказов."""
        params = clean_params({
            "start_date": to_iso8601(start_date) if start_date else None,
            "end_date": to_iso8601(end_date) if end_date else None,
            "page_count": page_count,
            "page_number": page_number,
            "status": status,
            "order_number": order_number,
            "order_id": order_id,
        })
        resp = self.http.get(
            f"/hs/api/v1/order_list/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def order_status_list(self, salon_id: str) -> Any:
        """GET order_status_list — статусы заказов."""
        resp = self.http.get(f"/hs/api/v1/order_status_list/{salon_id}")
        return self.data(resp)

    def deposit_detail(
        self,
        salon_id: str,
        deposit_id: str,
        page_count: Optional[int] = None,
        page_number: Optional[int] = None,
    ) -> Any:
        """GET deposit_detail — движения по счёту."""
        params = clean_params({
            "deposit_id": deposit_id,
            "page_count": page_count,
            "page_number": page_number,
        })
        resp = self.http.get(f"/hs/api/v1/deposit_detail/{salon_id}/", params=params)
        return self.data(resp)

    def delivery_list(self, salon_id: str) -> Any:
        """GET delivery_list — услуги доставки."""
        resp = self.http.get(f"/hs/api/v1/delivery_list/{salon_id}")
        return self.data(resp)

    def filter_list(self, salon_id: str) -> Any:
        """GET filter_list — фильтры товаров."""
        resp = self.http.get(f"/hs/api/v1/filter_list/{salon_id}")
        return self.data(resp)