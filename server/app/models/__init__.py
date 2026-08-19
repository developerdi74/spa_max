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

__all__ = [
    "NewsletterStatus",
    "NewsletterBase",
    "NewsletterCreate",
    "NewsletterUpdate",
    "NewsletterDocument",
    "NewsletterLog",
]
