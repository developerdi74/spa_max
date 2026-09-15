"""
Модели данных.
"""

from .newsletter import (
    NewsletterStatus,
    NewsletterBase,
    NewsletterCreate,
    NewsletterUpdate,
    NewsletterDocument,
    NewsletterLog,
)
from .share import (
    ShareStatus,
    ShareBase,
    ShareCreate,
    ShareUpdate,
    ShareDocument,
)

__all__ = [
    "NewsletterStatus",
    "NewsletterBase",
    "NewsletterCreate",
    "NewsletterUpdate",
    "NewsletterDocument",
    "NewsletterLog",
    "ShareStatus",
    "ShareBase",
    "ShareCreate",
    "ShareUpdate",
    "ShareDocument",
]
