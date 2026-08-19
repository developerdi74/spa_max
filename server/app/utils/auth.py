"""
Модуль для простой базовой авторизации.
"""

import logging
from functools import wraps
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config.settings import settings

logger = logging.getLogger(__name__)


class AuthRouter:
    """Роутер для управления авторизацией."""
    
    def __init__(self, templates: Jinja2Templates):
        self.router = APIRouter()
        self.templates = templates
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Настройка маршрутов."""
        
        @self.router.get("/login", response_class=HTMLResponse)
        async def login_page(request: Request):
            """Страница входа."""
            return self.templates.TemplateResponse(
                request=request,
                name="auth/login.html",
                context={}
            )
        
        @self.router.post("/login", response_class=HTMLResponse)
        async def login_submit(
            request: Request,
            username: str = Form(...),
            password: str = Form(...)
        ):
            """Обработка формы входа."""
            if check_auth(username, password):
                # Успешная аутентификация - устанавливаем сессию
                request.session["authenticated"] = True
                request.session["username"] = username
                logger.info(f"✅ Пользователь {username} успешно вошел в систему")
                return RedirectResponse("/newsletters", status_code=303)
            else:
                # Неверные учетные данные
                logger.warning(f"❌ Неудачная попытка входа для пользователя: {username}")
                return self.templates.TemplateResponse(
                    request=request,
                    name="auth/login.html",
                    context={"error": "Неверное имя пользователя или пароль"},
                    status_code=401
                )
        
        @self.router.get("/logout", response_class=RedirectResponse)
        async def logout(request: Request):
            """Выход из системы."""
            username = request.session.get("username", "unknown")
            request.session.clear()
            logger.info(f"👋 Пользователь {username} вышел из системы")
            return RedirectResponse("/login", status_code=303)


def check_auth(username: str, password: str) -> bool:
    """Проверка учетных данных."""
    if not settings.ADMIN_PASSWORD:
        # Если пароль не установлен - разрешаем вход без проверки
        return True
    return (
        username == settings.ADMIN_USERNAME and
        password == settings.ADMIN_PASSWORD
    )


def login_required(func):
    """Декоратор для защиты роутов авторизацией."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Проверяем сессию
        session = request.session
        
        # Если пароль не установлен - пропускаем всех
        if not settings.ADMIN_PASSWORD:
            return await func(request, *args, **kwargs)
        
        if not session.get("authenticated"):
            # Если не аутентифицирован - редирект на страницу входа
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login"}
            )
        
        return await func(request, *args, **kwargs)
    
    return wrapper
