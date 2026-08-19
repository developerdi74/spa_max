"""
Роутеры для обработки HTTP-запросов.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..models.newsletter import NewsletterDocument, NewsletterStatus, NewsletterCreate
from ..repositories.database import DatabaseManager
from ..services.newsletter_service import NewsletterService
from ..config.settings import settings

logger = logging.getLogger(__name__)


def is_valid_object_id(value: str) -> bool:
    """Проверка валидности MongoDB ObjectId."""
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def normalize_newsletter(doc: NewsletterDocument) -> Dict[str, Any]:
    """Нормализация данных рассылки для отображения."""
    return {
        "_id": doc.id,
        "name": doc.name,
        "text": doc.text,
        "status": doc.status.value,
        "attempt": doc.attempt,
        "sentCount": doc.sentCount,
        "errorCount": doc.errorCount,
        "createdAt": doc.createdAt,
        "updatedAt": doc.updatedAt,
        "startedAt": doc.startedAt,
        "finishedAt": doc.finishedAt,
        "error": doc.error,
    }


class NewsletterRouter:
    """Роутер для управления рассылками."""
    
    def __init__(self, templates: Jinja2Templates):
        self.router = APIRouter()
        self.templates = templates
        self.db_manager: Optional[DatabaseManager] = None
        self.newsletter_service: Optional[NewsletterService] = None
        
        self._setup_routes()
    
    def initialize(self, db_manager: DatabaseManager, newsletter_service: NewsletterService) -> None:
        """Инициализация зависимостей роутера."""
        self.db_manager = db_manager
        self.newsletter_service = newsletter_service
    
    def _setup_routes(self) -> None:
        """Настройка маршрутов."""
        
        @self.router.get("/newsletters", response_class=HTMLResponse)
        async def newsletters_list(request: Request):
            """Список всех рассылок."""
            if not self.db_manager or not self.db_manager.newsletters:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            items = await self.db_manager.newsletters.get_all(limit=200)
            normalized_items = [normalize_newsletter(item) for item in items]
            
            has_active = any(
                item.get("status") in [NewsletterStatus.queued.value, NewsletterStatus.running.value]
                for item in normalized_items
            )
            
            return self.templates.TemplateResponse(
                request=request,
                name="newsletters/list.html",
                context={
                    "items": normalized_items,
                    "has_active": has_active,
                }
            )
        
        @self.router.get("/newsletters/new", response_class=HTMLResponse)
        async def newsletter_new(request: Request):
            """Форма создания новой рассылки."""
            return self.templates.TemplateResponse(
                request=request,
                name="newsletters/form.html",
                context={
                    "mode": "create",
                    "newsletter": None,
                    "id": None,
                }
            )
        
        @self.router.post("/newsletters", response_class=HTMLResponse)
        async def newsletter_create(
            request: Request,
            name: str = Form(...),
            text: str = Form(...)
        ):
            """Создание новой рассылки."""
            if not self.db_manager or not self.db_manager.newsletters:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not name.strip() or not text.strip():
                raise HTTPException(status_code=400, detail="Название и текст обязательны")
            
            newsletter = NewsletterDocument(
                name=name.strip(),
                text=text.strip(),
                status=NewsletterStatus.draft,
                attempt=0,
                sentCount=0,
                errorCount=0,
                createdAt=datetime.now(),
                updatedAt=datetime.now(),
            )
            
            await self.db_manager.newsletters.create(newsletter)
            
            return RedirectResponse("/newsletters", status_code=303)
        
        @self.router.post("/newsletters/{newsletter_id}", response_class=HTMLResponse)
        async def newsletter_update(
            request: Request,
            newsletter_id: str,
            name: str = Form(...),
            text: str = Form(...)
        ):
            """Обновление существующей рассылки."""
            if not self.db_manager or not self.db_manager.newsletters:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(newsletter_id):
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            if not name.strip() or not text.strip():
                raise HTTPException(status_code=400, detail="Название и текст обязательны")
            
            newsletter = await self.db_manager.newsletters.get_by_id(newsletter_id)
            if not newsletter:
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            if not await self.newsletter_service.validate_newsletter_status_for_edit(newsletter):
                raise HTTPException(
                    status_code=409,
                    detail="Нельзя редактировать рассылку, которая уже в очереди или отправляется"
                )
            
            from ..models.newsletter import NewsletterUpdate
            update_data = NewsletterUpdate(name=name.strip(), text=text.strip())
            await self.db_manager.newsletters.update(newsletter_id, update_data)
            
            return RedirectResponse("/newsletters", status_code=303)
        
        @self.router.post("/newsletters/{newsletter_id}/delete", response_class=HTMLResponse)
        async def newsletter_delete(newsletter_id: str):
            """Удаление рассылки."""
            if not self.db_manager or not self.db_manager.newsletters:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(newsletter_id):
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            newsletter = await self.db_manager.newsletters.get_by_id(newsletter_id)
            if not newsletter:
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            if not await self.newsletter_service.validate_newsletter_status_for_delete(newsletter):
                raise HTTPException(
                    status_code=409,
                    detail="Нельзя удалить рассылку, которая уже в очереди или отправляется"
                )
            
            await self.db_manager.newsletters.delete(newsletter_id)
            
            return RedirectResponse("/newsletters", status_code=303)
        
        @self.router.get("/newsletters/{newsletter_id}/edit", response_class=HTMLResponse)
        async def newsletter_edit(request: Request, newsletter_id: str):
            """Форма редактирования рассылки."""
            if not self.db_manager or not self.db_manager.newsletters:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(newsletter_id):
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            newsletter = await self.db_manager.newsletters.get_by_id(newsletter_id)
            if not newsletter:
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            return self.templates.TemplateResponse(
                request=request,
                name="newsletters/form.html",
                context={
                    "mode": "edit",
                    "newsletter": normalize_newsletter(newsletter),
                    "id": newsletter_id,
                }
            )
        
        @self.router.post("/newsletters/{newsletter_id}/send", response_class=HTMLResponse)
        async def newsletter_send(newsletter_id: str, background_tasks: BackgroundTasks):
            """Запуск рассылки."""
            if not self.db_manager or not self.db_manager.newsletters:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(newsletter_id):
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            newsletter = await self.db_manager.newsletters.get_by_id(newsletter_id)
            
            if not newsletter:
                raise HTTPException(status_code=404, detail="Рассылка не найдена")
            
            if not await self.newsletter_service.validate_newsletter_status_for_send(newsletter):
                raise HTTPException(
                    status_code=409,
                    detail="Рассылка уже в очереди или отправляется"
                )
            
            new_attempt = int(newsletter.attempt) + 1
            
            await self.db_manager.newsletters.mark_as_queued(newsletter_id, new_attempt)
            
            # Запуск фоновой задачи
            background_tasks.add_task(
                self.newsletter_service.send_newsletter,
                newsletter_id,
                new_attempt
            )
            
            return RedirectResponse("/newsletters", status_code=303)


class HealthRouter:
    """Роутер для проверки здоровья сервиса."""
    
    def __init__(self):
        self.router = APIRouter()
        self.db_manager: Optional[DatabaseManager] = None
        
        self._setup_routes()
    
    def initialize(self, db_manager: DatabaseManager) -> None:
        """Инициализация зависимостей роутера."""
        self.db_manager = db_manager
    
    def _setup_routes(self) -> None:
        """Настройка маршрутов."""
        
        @self.router.get("/")
        async def root():
            """Корневой эндпоинт."""
            return {"status": "ok", "timestamp": datetime.now().isoformat()}
        
        @self.router.get("/health")
        async def health_check():
            """Проверка здоровья сервиса."""
            health = {"status": "ok", "checks": {}}
            
            if self.db_manager:
                db_health = await self.db_manager.health_check()
                health["checks"]["mongodb"] = db_health.get("mongodb", "unknown")
                if db_health.get("mongodb") != "ok":
                    health["status"] = "degraded"
            
            return health
