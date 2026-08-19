"""Главный клиент SDK 1С:SPA-Салон."""

from __future__ import annotations

from typing import Optional

from .http import DEFAULT_BASE_URL, HTTPClient
from .resources import (
    AuthorizationResource, BookingsResource, ClientsResource,
    OnlineStoreResource, PaymentsResource, ReviewsResource,
    SalesResource, SalonsResource, ServicesResource,
    StaffResource, TerminalResource, VisitsResource,
)


class SalonClient:
    """Точка входа в SDK.

    Пример:
        client = SalonClient(api_key="...", salon_id="...")
        services = client.bookings.book_services()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        basic_auth: Optional[tuple] = None,
        salon_id: Optional[str] = None,
        usertoken: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 0,
    ):
        self.http = HTTPClient(
            base_url=base_url,
            api_key=api_key,
            basic_auth=basic_auth,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.salon_id = salon_id
        self.usertoken = usertoken

        # Ресурсы ------------------------------------------------------- #
        self.auth = AuthorizationResource(self)
        self.bookings = BookingsResource(self)
        self.visits = VisitsResource(self)
        self.payments = PaymentsResource(self)
        self.sales = SalesResource(self)
        self.clients = ClientsResource(self)
        self.salons = SalonsResource(self)
        self.services = ServicesResource(self)
        self.reviews = ReviewsResource(self)
        self.store = OnlineStoreResource(self)
        self.terminal = TerminalResource(self)
        self.staff = StaffResource(self)

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "SalonClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()