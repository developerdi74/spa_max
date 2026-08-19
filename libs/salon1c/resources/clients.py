"""Клиенты."""

from __future__ import annotations

from typing import Any, List, Optional

from ..utils import clean_params
from .base import BaseResource


class ClientsResource(BaseResource):

    # ---------- Получение / создание / изменение ---------- #
    def get_client(self, salon_id: str, usertoken: Optional[str] = None) -> Any:
        """GET client — информация о клиенте по UserToken."""
        resp = self.http.get(
            f"/hs/api/v1/client/{salon_id}/",
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def create_client(
        self,
        salon_id: str,
        phone: str,
        usertoken: Optional[str] = None,
        **fields: Any,
    ) -> Any:
        """POST client — создание клиента."""
        body = {"phone": phone, **fields}
        resp = self.http.post(
            f"/hs/api/v1/client/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def update_client_by_id(
        self,
        client_id: str,
        usertoken: Optional[str] = None,
        **fields: Any,
    ) -> Any:
        """PUT client — изменение клиента по ID."""
        body = {"id": client_id, **fields}
        resp = self.http.put(
            "/hs/api/v1/client/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def search_clients(
        self,
        salon_id: str,
        body: Optional[dict] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """POST clients — поиск клиентов (фильтры, пагинация, поля)."""
        resp = self.http.post(
            f"/hs/api/v1/clients/{salon_id}/",
            json_body=body or {},
            usertoken=self.token(usertoken),
        )
        return resp  # вместе с Meta

    def update_client(
        self,
        salon_id: str,
        usertoken: Optional[str] = None,
        **fields: Any,
    ) -> Any:
        """POST update_client — обновить данные текущего клиента."""
        resp = self.http.post(
            f"/hs/api/v1/update_client/{salon_id}",
            json_body=fields,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    # ---------- Счета ---------- #
    def deposit_list(
        self,
        salon_id: str,
        with_advance: Optional[bool] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET deposit_list — лицевые и бонусные счета клиента."""
        params = clean_params({"with_advance": with_advance})
        resp = self.http.get(
            f"/hs/api/v1/deposit_list/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def refill_deposit(
        self,
        salon_id: str,
        transaction_id: str,
        deposit_id: str,
        cost: float,
        usertoken: Optional[str] = None,
    ) -> Any:
        """POST refill_deposit — пополнение лицевого счёта."""
        body = {
            "transaction_id": transaction_id,
            "deposit_id": deposit_id,
            "cost": cost,
        }
        resp = self.http.post(
            f"/hs/api/v1/refill_deposit/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    # ---------- История / визиты ---------- #
    def records_history(self, salon_id: str, usertoken: Optional[str] = None) -> Any:
        """GET records_history — история оконченных визитов клиента."""
        resp = self.http.get(
            f"/hs/api/v1/records_history/{salon_id}/",
            usertoken=self.token(usertoken),
        )
        print(resp)
        return self.data(resp)

    def planned_records(self, salon_id: str, usertoken: Optional[str] = None) -> Any:
        """GET records — запланированные визиты клиента."""
        resp = self.http.get(
            f"/hs/api/v1/records/{salon_id}/",
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    # ---------- Пакеты услуг и сертификаты ---------- #
    def tickets(self, salon_id: str, usertoken: Optional[str] = None) -> Any:
        """GET tickets — пакеты услуг и разовые услуги клиента."""
        resp = self.http.get(
            f"/hs/api/v1/tickets/{salon_id}",
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def ticket(
        self,
        salon_id: str,
        ticket_id: str,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET ticket — подробное описание пакета услуг."""
        resp = self.http.get(
            f"/hs/api/v1/ticket/{salon_id}/",
            params={"id": ticket_id},
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def certificates(self, salon_id: str, usertoken: Optional[str] = None) -> Any:
        """GET certificates — приобретённые сертификаты."""
        resp = self.http.get(
            f"/hs/api/v1/certificates/{salon_id}",
            usertoken=self.token(usertoken),
        )
        return self.data(resp)