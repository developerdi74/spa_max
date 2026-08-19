"""Сотрудники и графики работы."""

from __future__ import annotations

from typing import Any, List, Optional

from ..utils import to_iso8601
from .base import BaseResource


class StaffResource(BaseResource):

    def work_schedule(
        self,
        salon_id: str,
        staff_id: str,
        start_date,
        end_date,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET work_schedule — график работы сотрудника."""
        params = {
            "staff_id": staff_id,
            "start_date": to_iso8601(start_date),
            "end_date": to_iso8601(end_date),
        }
        resp = self.http.get(
            f"/hs/api/v1/work_schedule/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def update_work_schedule(
        self,
        salon_id: str,
        staff_id: str,
        items: List[dict],
        usertoken: Optional[str] = None,
    ) -> Any:
        """PUT work_schedule — редактирование графика работы.

        items: [{date, times: [{begin, end, type}], ...}]
        """
        body = {"staff_id": staff_id, "items": items}
        resp = self.http.put(
            f"/hs/api/v1/work_schedule/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)