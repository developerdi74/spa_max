"""
Роутеры для обработки HTTP-запросов вопросов и ответов (FAQ).
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..models.faq import FaqDocument, FaqStatus, FaqCreate, FaqUpdate
from ..repositories.database import DatabaseManager
from ..config.settings import settings
from ..utils.auth import login_required

logger = logging.getLogger(__name__)


def is_valid_object_id(value: str) -> bool:
    """Проверка валидности MongoDB ObjectId."""
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def normalize_faq(doc: FaqDocument) -> Dict[str, Any]:
    """Нормализация данных вопроса для отображения."""
    return {
        "_id": doc.id,
        "question": doc.question,
        "answer": doc.answer,
        "category": doc.category,
        "status": doc.status.value,
        "active": doc.active,
        "createdAt": doc.createdAt,
        "updatedAt": doc.updatedAt,
    }


class FaqRouter:
    """Роутер для управления вопросами и ответами."""
    
    def __init__(self, templates: Jinja2Templates):
        self.router = APIRouter()
        self.templates = templates
        self.db_manager: Optional[DatabaseManager] = None
        
        self._setup_routes()
    
    def initialize(self, db_manager: DatabaseManager) -> None:
        """Инициализация зависимостей роутера."""
        self.db_manager = db_manager
    
    def _setup_routes(self) -> None:
        """Настройка маршрутов."""
        
        @self.router.get("/faq", response_class=HTMLResponse)
        @login_required
        async def faq_list(request: Request):
            """Список всех вопросов и ответов."""
            if not self.db_manager or not self.db_manager.faqs:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            items = await self.db_manager.faqs.get_all(limit=200)
            normalized_items = [normalize_faq(item) for item in items]
            
            return self.templates.TemplateResponse(
                request=request,
                name="faq/list.html",
                context={
                    "items": normalized_items,
                }
            )
        
        @self.router.get("/faq/new", response_class=HTMLResponse)
        @login_required
        async def faq_new(request: Request):
            """Форма создания нового вопроса."""
            return self.templates.TemplateResponse(
                request=request,
                name="faq/form.html",
                context={
                    "mode": "create",
                    "faq": None,
                    "id": None,
                }
            )
        
        @self.router.post("/faq", response_class=HTMLResponse)
        @login_required
        async def faq_create(
            request: Request,
            question: str = Form(...),
            answer: str = Form(...),
            category: str = Form(None),
            active: str = Form(None)
        ):
            """Создание нового вопроса."""
            if not self.db_manager or not self.db_manager.faqs:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not question.strip() or not answer.strip():
                raise HTTPException(status_code=400, detail="Вопрос и ответ обязательны")
            
            is_active = active == "on"
            
            faq = FaqDocument(
                question=question.strip(),
                answer=answer.strip(),
                category=category.strip() if category else None,
                status=FaqStatus.draft,
                active=is_active,
                createdAt=datetime.now(),
                updatedAt=datetime.now(),
            )
            
            await self.db_manager.faqs.create(faq)
            
            return RedirectResponse("/faq", status_code=303)
        
        @self.router.post("/faq/{faq_id}", response_class=HTMLResponse)
        @login_required
        async def faq_update(
            request: Request,
            faq_id: str,
            question: str = Form(...),
            answer: str = Form(...),
            category: str = Form(None),
            active: str = Form(None)
        ):
            """Обновление существующего вопроса."""
            if not self.db_manager or not self.db_manager.faqs:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(faq_id):
                raise HTTPException(status_code=404, detail="Вопрос не найден")
            
            if not question.strip() or not answer.strip():
                raise HTTPException(status_code=400, detail="Вопрос и ответ обязательны")
            
            faq = await self.db_manager.faqs.get_by_id(faq_id)
            if not faq:
                raise HTTPException(status_code=404, detail="Вопрос не найден")
            
            is_active = active == "on"
            
            update_data = FaqUpdate(
                question=question.strip(),
                answer=answer.strip(),
                category=category.strip() if category else None,
                active=is_active
            )
            await self.db_manager.faqs.update(faq_id, update_data)
            
            return RedirectResponse("/faq", status_code=303)
        
        @self.router.post("/faq/{faq_id}/delete", response_class=HTMLResponse)
        @login_required
        async def faq_delete(faq_id: str):
            """Удаление вопроса."""
            if not self.db_manager or not self.db_manager.faqs:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(faq_id):
                raise HTTPException(status_code=404, detail="Вопрос не найден")
            
            faq = await self.db_manager.faqs.get_by_id(faq_id)
            if not faq:
                raise HTTPException(status_code=404, detail="Вопрос не найден")
            
            await self.db_manager.faqs.delete(faq_id)
            
            return RedirectResponse("/faq", status_code=303)
        
        @self.router.get("/faq/{faq_id}/edit", response_class=HTMLResponse)
        @login_required
        async def faq_edit(request: Request, faq_id: str):
            """Форма редактирования вопроса."""
            if not self.db_manager or not self.db_manager.faqs:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(faq_id):
                raise HTTPException(status_code=404, detail="Вопрос не найден")
            
            faq = await self.db_manager.faqs.get_by_id(faq_id)
            if not faq:
                raise HTTPException(status_code=404, detail="Вопрос не найден")
            
            normalized_faq = normalize_faq(faq)
            normalized_faq["active"] = faq.active
            
            return self.templates.TemplateResponse(
                request=request,
                name="faq/form.html",
                context={
                    "mode": "edit",
                    "faq": normalized_faq,
                    "id": faq_id,
                }
            )
