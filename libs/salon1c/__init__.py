"""SDK для работы с API 1С:SPA-Салон, редакция 3.0."""

from .client import SalonClient
from .exceptions import (
    AuthorizationError, BadRequestError, InternalServerError,
    NotFoundError, SalonAPIError, SalonError, TransportError,
)
from .utils import make_sign, services_array_json, to_iso8601

__version__ = "1.0.0"
__all__ = [
    "SalonClient",
    "SalonError", "SalonAPIError", "AuthorizationError",
    "BadRequestError", "InternalServerError", "NotFoundError",
    "TransportError",
    "make_sign", "services_array_json", "to_iso8601",
    "__version__",
]