"""
Модели данных для работы с рассылками.
"""

from datetime import datetime
from typing import Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field


class NewsletterStatus(str, Enum):
    """Статусы рассылки."""
    draft = "draft"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class NewsletterBase(BaseModel):
    """Базовая модель рассылки."""
    name: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)


class NewsletterCreate(NewsletterBase):
    """Модель создания рассылки."""
    pass


class NewsletterUpdate(NewsletterBase):
    """Модель обновления рассылки."""
    pass


class NewsletterDocument(BaseModel):
    """Модель документа рассылки в MongoDB."""
    id: Optional[str] = None
    name: str
    text: str
    status: NewsletterStatus = NewsletterStatus.draft
    attempt: int = 0
    sentCount: int = 0
    errorCount: int = 0
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None
    error: Optional[str] = None
    
    class Config:
        populate_by_name = True
    
    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "NewsletterDocument":
        """Конвертация документа MongoDB в модель."""
        return cls(
            id=str(doc.get("_id", "")),
            name=doc.get("name", ""),
            text=doc.get("text", ""),
            status=NewsletterStatus(doc.get("status", NewsletterStatus.draft.value)),
            attempt=doc.get("attempt", 0),
            sentCount=doc.get("sentCount", 0),
            errorCount=doc.get("errorCount", 0),
            createdAt=doc.get("createdAt"),
            updatedAt=doc.get("updatedAt"),
            startedAt=doc.get("startedAt"),
            finishedAt=doc.get("finishedAt"),
            error=doc.get("error"),
        )
    
    def to_mongo(self) -> Dict[str, Any]:
        """Конвертация модели в документ MongoDB."""
        return {
            "name": self.name,
            "text": self.text,
            "status": self.status.value,
            "attempt": self.attempt,
            "sentCount": self.sentCount,
            "errorCount": self.errorCount,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
            "startedAt": self.startedAt,
            "finishedAt": self.finishedAt,
            "error": self.error,
        }


class NewsletterLog(BaseModel):
    """Модель лога отправки рассылки."""
    newsletterId: str
    attempt: int
    chatId: str
    sent: bool
    date: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_mongo(self) -> Dict[str, Any]:
        """Конвертация модели в документ MongoDB."""
        return {
            "newsletterId": self.newsletterId,
            "attempt": self.attempt,
            "chatId": self.chatId,
            "sent": self.sent,
            "date": self.date,
            "error": self.error,
        }
