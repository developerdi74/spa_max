"""Визиты."""

from __future__ import annotations

from typing import Any, Optional

from ..utils import clean_params, to_iso8601
from .base import BaseResource


class VisitsResource(BaseResource):

    def finished_visits(
        self,
        salon_id: str,
        start_date=None,
        end_date=None,
        ticket_id: Optional[str] = None,
    ) -> Any:
        """GET finished_visites — оконченные визиты."""
        params = clean_params({
            "start_date": to_iso8601(start_date) if start_date else None,
            "end_date": to_iso8601(end_date) if end_date else None,
            "ticket_id": ticket_id,
        })
        resp = self.http.get(f"/hs/api/v1/finished_visites/{salon_id}/", params=params)
        return self.data(resp)

    def visits(
        self,
        salon_id: str,
        start_date=None,
        end_date=None,
        ticket_id: Optional[str] = None,
    ) -> Any:
        """GET visites — список визитов."""
        params = clean_params({
            "start_date": to_iso8601(start_date) if start_date else None,
            "end_date": to_iso8601(end_date) if end_date else None,
            "ticket_id": ticket_id,
        })
        resp = self.http.get(f"/hs/api/v1/visites/{salon_id}/", params=params)
        return self.data(resp)

    def update_record(
        self,
        record: dict,
        usertoken: Optional[str] = None,
    ) -> Any:
        """PUT records — изменение записи.

        record должен содержать id и изменяемые поля
        (datetime, comment, status, duration, record_array).
        """
        resp = self.http.put(
            "/hs/api/v1/records/{salon_id}/",
            json_body=record,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def records_list(
        self,
        salon_id: str,
        page: Optional[int] = None,
        count: Optional[int] = None,
        id: Optional[str] = None,
        client_id: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET records_list — информация о записях (с пагинацией)."""
        params = clean_params({
            "page": page, "count": count,
            "id": id, "client_id": client_id,
        })
        resp = self.http.get(
            f"/hs/api/v1/records_list/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return resp  # возвращаем вместе с Meta