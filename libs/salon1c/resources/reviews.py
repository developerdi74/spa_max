# resources/reviews.py
from __future__ import annotations
from typing import Any, Optional
from ..utils import clean_params, to_iso8601
from .base import BaseResource


class ReviewsResource(BaseResource):

    def rate_record(
        self,
        salon_id: str,
        record_id: str,
        staff_id: str,
        rating: int,
        comment: Optional[str] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """POST record_rating — оценка визита (0–10)."""
        body = {
            "record_id": record_id,
            "staff_id": staff_id,
            "rating": rating,
            "comment": comment or "",
        }
        resp = self.http.post(
            f"/hs/api/v1/record_rating/{salon_id}",
            json_body=body,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)

    def comments(
        self,
        salon_id: str,
        start_date=None,
        end_date=None,
        staff_id: Optional[str] = None,
        rating: Optional[int] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        usertoken: Optional[str] = None,
    ) -> Any:
        """GET comments — оценки и комментарии клиентов."""
        params = clean_params({
            "start_date": to_iso8601(start_date) if start_date else None,
            "end_date": to_iso8601(end_date) if end_date else None,
            "staff_id": staff_id,
            "rating": rating,
            "page": page,
            "page_size": page_size,
        })
        resp = self.http.get(
            f"/hs/api/v1/comments/{salon_id}/",
            params=params,
            usertoken=self.token(usertoken),
        )
        return self.data(resp)