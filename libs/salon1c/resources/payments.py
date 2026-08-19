"""Оплаты визитов."""

from __future__ import annotations

from typing import Any, List, Optional

from .base import BaseResource


class PaymentsResource(BaseResource):

    def debt_visits(self, salon_id: str) -> Any:
        """GET debt_visits — визиты с долгами."""
        resp = self.http.get(f"/hs/api/v1/debt_visits/{salon_id}")
        return self.data(resp)

    def pay_visit(
        self,
        salon_id: str,
        record_id: str,
        transaction_id: str,
        payment_list: List[dict],
        usertoken: Optional[str] = None,
    ) -> Any:
        """POST visit_payment — оплата визита.

        payment_list: [{type: card|cash|deposit|bonus, amount, id?}, ...]
        """
        body = {
            "record_id": record_id,
            "transaction_id": transaction_id,
            "payment_list": payment_list,
        }
        resp = self.http.post(
            f"/hs/api/v1/visit_payment/{salon_id}/",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)