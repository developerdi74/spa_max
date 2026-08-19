"""
Репозитории.
"""

from .database import (
    BaseRepository,
    NewsletterRepository,
    NewsletterLogRepository,
    UserRepository,
    DatabaseManager,
)

__all__ = [
    "BaseRepository",
    "NewsletterRepository",
    "NewsletterLogRepository",
    "UserRepository",
    "DatabaseManager",
]
