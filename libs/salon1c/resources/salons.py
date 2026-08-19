# resources/salons.py
from __future__ import annotations
from typing import Any, Optional
from .base import BaseResource


class SalonsResource(BaseResource):

    def get_salons(self, salon_id: str, usertoken: Optional[str] = None) -> Any:
        """GET salons — информация о салонах."""
        resp = self.http.get(
            f"/hs/api/v1/salons/{salon_id}/",
            usertoken=self.token(usertoken),
        )
        return self.data(resp)