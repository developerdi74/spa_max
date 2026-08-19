# resources/services.py
from __future__ import annotations
from typing import Any, Optional
from ..utils import clean_params
from .base import BaseResource


class ServicesResource(BaseResource):

    def get_services(
        self,
        salon_id: str,
        service_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        category_id: Optional[str] = None,
        page: Optional[int] = None,
        count: Optional[int] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET services — услуги салона с ценами и мастерами."""
        params = clean_params({
            "service_id": service_id,
            "staff_id": staff_id,
            "category_id": category_id,
            "page": page,
            "count": count,
        })
        resp = self.http.get(
            f"/hs/api/v1/services/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return resp  # вместе с Meta