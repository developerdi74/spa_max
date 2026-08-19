"""
Модели данных для работы с акциями.
"""

from datetime import datetime
from typing import Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field


class ShareStatus(str, Enum):
    """Статусы акции."""
    draft = "draft"
    active = "active"
    archived = "archived"


class ShareBase(BaseModel):
    """Базовая модель акции."""
    name: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)
    service_id: Optional[str] = Field(None, max_length=255)
    service_name: Optional[str] = Field(None, max_length=255)


class ShareCreate(ShareBase):
    """Модель создания акции."""
    pass


class ShareUpdate(ShareBase):
    """Модель обновления акции."""
    pass


class ShareDocument(BaseModel):
    """Модель документа акции в MongoDB."""
    id: Optional[str] = None
    name: str
    text: str
    service_id: Optional[str] = None
    service_name: Optional[str] = None
    status: ShareStatus = ShareStatus.draft
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
    
    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "ShareDocument":
        """Конвертация документа MongoDB в модель."""
        return cls(
            id=str(doc.get("_id", "")),
            name=doc.get("name", ""),
            text=doc.get("text", ""),
            service_id=doc.get("service_id"),
            service_name=doc.get("service_name"),
            status=ShareStatus(doc.get("status", ShareStatus.draft.value)),
            createdAt=doc.get("createdAt"),
            updatedAt=doc.get("updatedAt"),
        )
    
    def to_mongo(self) -> Dict[str, Any]:
        """Конвертация модели в документ MongoDB."""
        return {
            "name": self.name,
            "text": self.text,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "status": self.status.value,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }
