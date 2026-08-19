from .authorization import AuthorizationResource
from .bookings import BookingsResource
from .clients import ClientsResource
from .online_store import OnlineStoreResource
from .payments import PaymentsResource
from .reviews import ReviewsResource
from .sales import SalesResource
from .salons import SalonsResource
from .services import ServicesResource
from .staff import StaffResource
from .terminal import TerminalResource
from .visits import VisitsResource

__all__ = [
    "AuthorizationResource", "BookingsResource", "ClientsResource",
    "OnlineStoreResource", "PaymentsResource", "ReviewsResource",
    "SalesResource", "SalonsResource", "ServicesResource",
    "StaffResource", "TerminalResource", "VisitsResource",
]