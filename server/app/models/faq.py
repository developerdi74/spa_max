"""
Модели данных для работы с вопросами и ответами (FAQ).
"""

from datetime import datetime
from typing import Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field


class FaqStatus(str, Enum):
    """Статусы вопроса."""
    draft = "draft"
    active = "active"
    archived = "archived"


class FaqBase(BaseModel):
    """Базовая модель вопроса."""
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1)
    category: Optional[str] = Field(None, max_length=255)
    active: bool = True


class FaqCreate(FaqBase):
    """Модель создания вопроса."""
    pass


class FaqUpdate(FaqBase):
    """Модель обновления вопроса."""
    pass


class FaqDocument(BaseModel):
    """Модель документа вопроса в MongoDB."""
    id: Optional[str] = None
    question: str
    answer: str
    category: Optional[str] = None
    status: FaqStatus = FaqStatus.draft
    active: bool = True
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
    
    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "FaqDocument":
        """Конвертация документа MongoDB в модель."""
        return cls(
            id=str(doc.get("_id", "")),
            question=doc.get("question", ""),
            answer=doc.get("answer", ""),
            category=doc.get("category"),
            status=FaqStatus(doc.get("status", FaqStatus.draft.value)),
            active=doc.get("active", True),
            createdAt=doc.get("createdAt"),
            updatedAt=doc.get("updatedAt"),
        )
    
    def to_mongo(self) -> Dict[str, Any]:
        """Конвертация модели в документ MongoDB."""
        return {
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "status": self.status.value,
            "active": self.active,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }
