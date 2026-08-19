"""
Роутеры для обработки HTTP-запросов акций.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..models.share import ShareDocument, ShareStatus, ShareCreate, ShareUpdate
from ..repositories.database import DatabaseManager
from ..config.settings import settings

logger = logging.getLogger(__name__)


def is_valid_object_id(value: str) -> bool:
    """Проверка валидности MongoDB ObjectId."""
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def normalize_share(doc: ShareDocument) -> Dict[str, Any]:
    """Нормализация данных акции для отображения."""
    return {
        "_id": doc.id,
        "name": doc.name,
        "text": doc.text,
        "service_id": doc.service_id,
        "service_name": doc.service_name,
        "status": doc.status.value,
        "createdAt": doc.createdAt,
        "updatedAt": doc.updatedAt,
    }


class ShareRouter:
    """Роутер для управления акциями."""
    
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
        
        @self.router.get("/shares", response_class=HTMLResponse)
        async def shares_list(request: Request):
            """Список всех акций."""
            if not self.db_manager or not self.db_manager.shares:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            items = await self.db_manager.shares.get_all(limit=200)
            normalized_items = [normalize_share(item) for item in items]
            
            return self.templates.TemplateResponse(
                request=request,
                name="shares/list.html",
                context={
                    "items": normalized_items,
                }
            )
        
        @self.router.get("/shares/new", response_class=HTMLResponse)
        async def share_new(request: Request):
            """Форма создания новой акции."""
            services = []
            try:
                from listener.services.salon1c_service import Salon1CService
                salon_service = Salon1CService(
                    api_key=settings.SALON_API_KEY,
                    salon_id=settings.SALON_ID
                )
                services = await salon_service.get_book_services()
            except Exception as e:
                logger.warning(f"Не удалось загрузить услуги: {e}")
            
            return self.templates.TemplateResponse(
                request=request,
                name="shares/form.html",
                context={
                    "mode": "create",
                    "share": None,
                    "id": None,
                    "services": services,
                }
            )
        
        @self.router.post("/shares", response_class=HTMLResponse)
        async def share_create(
            request: Request,
            name: str = Form(...),
            text: str = Form(...),
            service_id: str = Form(None),
            service_name: str = Form(None),
            active: str = Form(None)
        ):
            """Создание новой акции."""
            if not self.db_manager or not self.db_manager.shares:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not name.strip() or not text.strip():
                raise HTTPException(status_code=400, detail="Название и текст обязательны")
            
            is_active = active == "on"
            
            share = ShareDocument(
                name=name.strip(),
                text=text.strip(),
                service_id=service_id.strip() if service_id else None,
                service_name=service_name.strip() if service_name else None,
                status=ShareStatus.draft,
                active=is_active,
                createdAt=datetime.now(),
                updatedAt=datetime.now(),
            )
            
            await self.db_manager.shares.create(share)
            
            return RedirectResponse("/shares", status_code=303)
        
        @self.router.post("/shares/{share_id}", response_class=HTMLResponse)
        async def share_update(
            request: Request,
            share_id: str,
            name: str = Form(...),
            text: str = Form(...),
            service_id: str = Form(None),
            service_name: str = Form(None),
            active: str = Form(None)
        ):
            """Обновление существующей акции."""
            if not self.db_manager or not self.db_manager.shares:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(share_id):
                raise HTTPException(status_code=404, detail="Акция не найдена")
            
            if not name.strip() or not text.strip():
                raise HTTPException(status_code=400, detail="Название и текст обязательны")
            
            share = await self.db_manager.shares.get_by_id(share_id)
            if not share:
                raise HTTPException(status_code=404, detail="Акция не найдена")
            
            is_active = active == "on"
            
            update_data = ShareUpdate(
                name=name.strip(),
                text=text.strip(),
                service_id=service_id.strip() if service_id else None,
                service_name=service_name.strip() if service_name else None,
                active=is_active
            )
            await self.db_manager.shares.update(share_id, update_data)
            
            return RedirectResponse("/shares", status_code=303)
        
        @self.router.post("/shares/{share_id}/delete", response_class=HTMLResponse)
        async def share_delete(share_id: str):
            """Удаление акции."""
            if not self.db_manager or not self.db_manager.shares:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(share_id):
                raise HTTPException(status_code=404, detail="Акция не найдена")
            
            share = await self.db_manager.shares.get_by_id(share_id)
            if not share:
                raise HTTPException(status_code=404, detail="Акция не найдена")
            
            await self.db_manager.shares.delete(share_id)
            
            return RedirectResponse("/shares", status_code=303)
        
        @self.router.get("/shares/{share_id}/edit", response_class=HTMLResponse)
        async def share_edit(request: Request, share_id: str):
            """Форма редактирования акции."""
            if not self.db_manager or not self.db_manager.shares:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            if not is_valid_object_id(share_id):
                raise HTTPException(status_code=404, detail="Акция не найдена")
            
            share = await self.db_manager.shares.get_by_id(share_id)
            if not share:
                raise HTTPException(status_code=404, detail="Акция не найдена")
            
            services = []
            try:
                from listener.services.salon1c_service import Salon1CService
                salon_service = Salon1CService(
                    api_key=settings.SALON_API_KEY,
                    salon_id=settings.SALON_ID
                )
                services = await salon_service.get_book_services()
            except Exception as e:
                logger.warning(f"Не удалось загрузить услуги: {e}")
            
            normalized_share = normalize_share(share)
            normalized_share["active"] = share.active
            
            return self.templates.TemplateResponse(
                request=request,
                name="shares/form.html",
                context={
                    "mode": "edit",
                    "share": normalized_share,
                    "id": share_id,
                    "services": services,
                }
            )
