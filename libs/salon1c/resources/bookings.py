"""Запись на визит."""

from __future__ import annotations

import logging

from datetime import date, datetime
from typing import Any, List, Optional, Sequence, Union

from ..utils import clean_params, services_array_json, to_iso8601
from .base import BaseResource

DateLike = Union[str, date, datetime]


class BookingsResource(BaseResource):

    def book_services(
        self,
        salon_id: str,
        staff_id: Optional[str] = None,
        datetime_: Optional[DateLike] = None,
        service_ids: Optional[Sequence[str]] = None,
    ) -> Any:
        """GET book_services — услуги, доступные для записи."""
        params = clean_params({
            "staff_id": staff_id,
            "datetime": to_iso8601(datetime_) if datetime_ else None,
            "service_ids": services_array_json(service_ids) if service_ids else None,
        })
        resp = self.http.get(f"/hs/api/v1/book_services/{salon_id}/", params=params)
        return self.data(resp)

    def book_staff(
        self,
        salon_id: str,
        service_id: Optional[str] = None,
        datetime_: Optional[DateLike] = None,
        service_ids: Optional[Sequence[str]] = None,
    ) -> Any:
        """GET book_staff — сотрудники, доступные для записи."""
        params = clean_params({
            "service_id": service_id,
            "datetime": to_iso8601(datetime_) if datetime_ else None,
            "service_ids": services_array_json(service_ids) if service_ids else None,
        })
        resp = self.http.get(f"/hs/api/v1/book_staff/{salon_id}/", params=params)
        return self.data(resp)

    def book_dates(
        self,
        salon_id: str,
        start_date: DateLike,
        end_date: DateLike,
        service_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        service_ids: Optional[Sequence[str]] = None,
    ) -> Any:
        """GET book_dates — даты, доступные для записи."""
        params = clean_params({
            "start_date": to_iso8601(start_date),
            "end_date": to_iso8601(end_date),
            "service_id": service_id,
            "staff_id": staff_id,
            "service_ids": services_array_json(service_ids) if service_ids else None,
        })
        resp = self.http.get(f"/hs/api/v1/book_dates/{salon_id}/", params=params)
        return self.data(resp)

    def book_times(
        self,
        salon_id: str,
        service_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        datetime_: Optional[DateLike] = None,
        service_ids: Optional[Sequence[str]] = None,
    ) -> Any:
        """GET book_times — слоты, доступные для записи."""
        params = clean_params({
            "service_id": service_id,
            "staff_id": staff_id,
            "datetime": to_iso8601(datetime_) if datetime_ else None,
            "service_ids": services_array_json(service_ids) if service_ids else None,
        })
        resp = self.http.get(f"/hs/api/v1/book_times/{salon_id}/", params=params)
        return self.data(resp)

    def recording_dates(
        self,
        salon_id: str,
        start_date: DateLike,
        end_date: DateLike,
        service_id: Optional[str] = None,
        staff_id: Optional[str] = None,
    ) -> Any:
        """GET recording_dates — даты записей по сотрудникам."""
        params = clean_params({
            "start_date": to_iso8601(start_date),
            "end_date": to_iso8601(end_date),
            "service_id": service_id,
            "staff_id": staff_id,
        })
        resp = self.http.get(f"/hs/api/v1/recording_dates/{salon_id}/", params=params)
        return self.data(resp)

    def book_record(
        self,
        salon_id: str,
        record_array: Optional[List[dict]] = None,
        usertoken: Optional[str] = None,
        **client_fields: Any,
    ) -> Any:
        """POST book_record — запись клиента на визит.

        record_array: [{datetime, service_id, staff_id}, ...]
        client_fields: fullname, name, last_name, second_name, birthday,
                       email, notify_by_sms, comment, commercial,
                       record_id, promocode
        """
        body = dict(client_fields)
        if record_array is not None:
            body["record_array"] = record_array
            
        resp = self.http.post(
            f"/hs/api/v1/book_record/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        logging.info(resp)
        return self.data(resp)

    def change_record(
        self,
        salon_id: str,
        record_id: str,
        datetime_: DateLike,
        usertoken: Optional[str] = None,
    ) -> Any:
        """PUT change_record — перенос визита."""
        params = {
            "record_id": record_id,
            "datetime": to_iso8601(datetime_),
        }
        resp = self.http.put(
            f"/hs/api/v1/change_record/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def cancel_record(
        self,
        salon_id: str,
        record_id: str,
        usertoken: Optional[str] = None,
    ) -> Any:
        """DELETE cancel_record — отмена записи."""
        resp = self.http.delete(
            f"/hs/api/v1/cancel_record/{salon_id}/",
            params={"record_id": record_id},
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def record_cost(
        self,
        salon_id: str,
        record_array: List[dict],
        promocode: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET record_cost — расчёт стоимости записи.

        record_array: [{datetime, service_id, staff_id}, ...]
        """
        import json as _json
        params = clean_params({
            "record_array": _json.dumps(record_array, ensure_ascii=False),
            "promocode": promocode,
        })
        resp = self.http.get(
            f"/hs/api/v1/record_cost/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)