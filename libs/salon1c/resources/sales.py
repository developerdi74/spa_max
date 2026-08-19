"""Продажи."""

from __future__ import annotations

from typing import Any, List, Optional

from .base import BaseResource


class SalesResource(BaseResource):

    def create_sale(
        self,
        salon_id: str,
        record_array: Optional[List[dict]] = None,
        usertoken: Optional[str] = None,
        **client_fields: Any,
    ) -> Any:
        """POST sale — создание продажи."""
        body = dict(client_fields)
        if record_array is not None:
            body["record_array"] = record_array
        resp = self.http.post(
            f"/hs/api/v1/sale/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def update_sale(
        self,
        sale_id: str,
        record_array: Optional[List[dict]] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """PUT sale — изменение продажи."""
        body = {"id": sale_id}
        if record_array is not None:
            body["record_array"] = record_array
        resp = self.http.put(
            "/hs/api/v1/sale/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def cancel_sale(
        self,
        salon_id: str,
        sale_id: str,
        usertoken: Optional[str] = None,
    ) -> Any:
        """DELETE sale — отмена продажи."""
        resp = self.http.delete(
            f"/hs/api/v1/sale/{salon_id}/",
            params={"id": sale_id},
            usertoken=self.token(usertoken),
        )
        return self.data(resp)