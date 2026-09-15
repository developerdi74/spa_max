"""
Роутер для отображения статистики.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from calendar import month_name

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..repositories.database import DatabaseManager
from ..utils.auth import login_required

logger = logging.getLogger(__name__)


class StatsRouter:
    """Роутер для просмотра статистики."""
    
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
        
        @self.router.get("/stats", response_class=HTMLResponse)
        @login_required
        async def stats_list(request: Request):
            """Просмотр статистики по users, visits, confirmations."""
            if not self.db_manager or not self.db_manager.storage:
                raise HTTPException(status_code=503, detail="MongoDB not initialized")
            
            # Получаем статистику за последние 12 месяцев
            users_stats = await self.db_manager.storage.get_users_stats(months=12)
            visits_stats = await self.db_manager.storage.get_visits_stats(months=12)
            confirmations_stats = await self.db_manager.storage.get_confirmations_stats(months=12)
            
            # Преобразуем в словари для удобного доступа
            users_by_month = {(item['year'], item['month']): item['count'] for item in users_stats}
            visits_by_month = {(item['year'], item['month']): item['count'] for item in visits_stats}
            confirmations_by_month = {(item['year'], item['month']): item['count'] for item in confirmations_stats}
            
            # Собираем все месяцы
            all_months = set(users_by_month.keys()) | set(visits_by_month.keys()) | set(confirmations_by_month.keys())
            
            # Формируем итоговую статистику по месяцам
            stats_by_month = []
            for year, month in sorted(all_months, reverse=True):
                month_name_ru = {
                    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
                }.get(month, str(month))
                
                stats_by_month.append({
                    'year': year,
                    'month': month,
                    'month_name': month_name_ru,
                    'users': users_by_month.get((year, month), 0),
                    'visits': visits_by_month.get((year, month), 0),
                    'confirmations': confirmations_by_month.get((year, month), 0),
                })
            
            # Общие totals
            total_users = sum(users_by_month.values())
            total_visits = sum(visits_by_month.values())
            total_confirmations = sum(confirmations_by_month.values())
            
            return self.templates.TemplateResponse(
                request=request,
                name="stats/stats.html",
                context={
                    "stats_by_month": stats_by_month,
                    "total_users": total_users,
                    "total_visits": total_visits,
                    "total_confirmations": total_confirmations,
                    "total_users_months": total_users,
                    "total_visits_months": total_visits,
                    "total_confirmations_months": total_confirmations,
                }
            )
