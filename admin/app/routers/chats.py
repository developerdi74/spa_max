"""
Рабочее место менеджера: живые чаты с подписчиками.

Маршруты:
    GET  /chats                    — очередь активных обращений (+ archived=1 — история)
    GET  /chats/{ticket_id}        — окно переписки конкретного чата
    POST /chats/{ticket_id}/assign — взять обращение в работу
    POST /chats/{ticket_id}/reply  — отправить ответ клиенту (сообщением бота)
    POST /chats/{ticket_id}/close  — закрыть обращение (клиент снова у бота)

Данные берутся из общей коллекции support_tickets (libs.chat_state),
ответы отправляются тем же токеном бота, что использует listener.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..repositories.database import DatabaseManager
from ..utils.auth import login_required

logger = logging.getLogger(__name__)


def _is_active(ticket: Dict[str, Any]) -> bool:
    return ticket.get("status") in ("open", "assigned")


def _decorate_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Приводит даты к строкам для шаблона и считает непрочитанное."""
    t = dict(ticket)
    for key in ("createdAt", "updatedAt", "clientLastActivity", "managerLastActivity", "closedAt"):
        val = t.get(key)
        t[key] = val.strftime("%d.%m.%Y %H:%M") if isinstance(val, datetime) else ""
    history = []
    last_manager_at = None
    for m in t.get("history", []):
        mm = dict(m)
        at = mm.get("at")
        mm["at"] = at.strftime("%d.%m.%Y %H:%M") if isinstance(at, datetime) else ""
        history.append(mm)
        if mm.get("author") == "manager" and isinstance(at, datetime):
            if last_manager_at is None or at > last_manager_at:
                last_manager_at = at
    # Сообщения клиента, пришедшие после последнего ответа менеджера
    unread = 0
    if _is_active(t):
        unread = sum(
            1
            for m in t.get("history", [])
            if m.get("author") == "client"
            and isinstance(m.get("at"), datetime)
            and (last_manager_at is None or m["at"] > last_manager_at)
        )
    t["unread"] = unread
    lm = t.get("lastMessage") or {}
    lm_text = (lm.get("text") or "").strip().replace("\n", " ")
    t["lastMessagePreview"] = lm_text[:80] + ("…" if len(lm_text) > 80 else "")
    t["lastMessageAuthor"] = lm.get("author", "")
    return t


class ChatRouter:
    """Роутер рабочего места менеджера."""

    def __init__(self, templates: Jinja2Templates, bot=None):
        self.router = APIRouter()
        self.templates = templates
        self.bot = bot
        self.db_manager: Optional[DatabaseManager] = None
        self._setup_routes()

    def initialize(self, db_manager: DatabaseManager, bot=None) -> None:
        """Инициализация зависимостей роутера."""
        self.db_manager = db_manager
        if bot is not None:
            self.bot = bot

    async def _get_tickets_repo(self):
        if not self.db_manager or not self.db_manager.support_tickets:
            raise HTTPException(status_code=503, detail="MongoDB not initialized")
        return self.db_manager.support_tickets

    async def _send_to_client(self, chat_id: int, text: str) -> bool:
        """Отправка сообщения клиенту от имени бота."""
        if self.bot is None:
            logger.error("Bot не инициализирован, сообщение не отправлено")
            return False
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в чат {chat_id}: {e}")
            return False

    def _setup_routes(self) -> None:

        @self.router.get("/chats", response_class=HTMLResponse)
        @login_required
        async def chats_list(request: Request):
            """Очередь активных обращений; ?archived=1 — закрытые."""
            repo = await self._get_tickets_repo()
            archived = request.query_params.get("archived") == "1"
            statuses = ("closed",) if archived else ("open", "assigned")
            tickets = await repo.list_tickets(statuses=statuses, limit=200)
            items = [_decorate_ticket(t) for t in tickets]
            stats = await repo.stats()
            return self.templates.TemplateResponse(
                request=request,
                name="chats/list.html",
                context={
                    "items": items,
                    "stats": stats,
                    "archived": archived,
                },
            )

        @self.router.get("/chats/{ticket_id}", response_class=HTMLResponse)
        @login_required
        async def chat_view(request: Request, ticket_id: str):
            """Окно переписки по тикету."""
            repo = await self._get_tickets_repo()
            ticket = await repo.get_ticket(ticket_id)
            if not ticket:
                raise HTTPException(status_code=404, detail="Обращение не найдено")
            t = _decorate_ticket(ticket)
            # История уже отсортирована как добавлялась; приводим к возрастанию
            history = sorted(
                [dict(m) for m in ticket.get("history", [])],
                key=lambda m: m.get("at") or datetime.min,
            )
            for m in history:
                at = m.get("at")
                m["at"] = at.strftime("%d.%m.%Y %H:%M") if isinstance(at, datetime) else ""
            t["history"] = history
            return self.templates.TemplateResponse(
                request=request,
                name="chats/view.html",
                context={"ticket": t},
            )

        @self.router.post("/chats/{ticket_id}/assign", response_class=HTMLResponse)
        @login_required
        async def chat_assign(request: Request, ticket_id: str):
            """Взять обращение в работу."""
            repo = await self._get_tickets_repo()
            manager = request.session.get("username", "manager")
            ticket = await repo.assign(ticket_id, manager=manager)
            if not ticket:
                raise HTTPException(status_code=404, detail="Обращение не найдено")
            return RedirectResponse(f"/chats/{ticket_id}", status_code=303)

        @self.router.post("/chats/{ticket_id}/reply", response_class=HTMLResponse)
        @login_required
        async def chat_reply(request: Request, ticket_id: str, text: str = Form(...)):
            """Ответ клиенту: пишем в историю тикета и шлём сообщение ботом."""
            repo = await self._get_tickets_repo()
            text = (text or "").strip()
            if not text:
                return RedirectResponse(f"/chats/{ticket_id}", status_code=303)

            ticket = await repo.get_ticket(ticket_id)
            if not ticket:
                raise HTTPException(status_code=404, detail="Обращение не найдено")

            manager = request.session.get("username", "manager")

            # Автоприсвоение: open -> assigned, если ещё не взят
            if ticket.get("status") == "open":
                await repo.assign(ticket_id, manager=manager)

            sent = await self._send_to_client(int(ticket["chatId"]), text)
            note = text if sent else f"{text}\n\n⚠️ (не отправлено клиенту)"
            await repo.append_message(ticket_id, author="manager", text=note, manager=manager)

            if not sent:
                logger.warning(f"Не удалось отправить ответ в чат {ticket['chatId']}")
            return RedirectResponse(f"/chats/{ticket_id}", status_code=303)

        @self.router.post("/chats/{ticket_id}/close", response_class=HTMLResponse)
        @login_required
        async def chat_close(request: Request, ticket_id: str):
            """Закрыть обращение — клиент возвращается к боту."""
            repo = await self._get_tickets_repo()
            manager = request.session.get("username", "manager")
            # Извлекаем chatId до закрытия (close может вернуть None, если тикет уже закрыт)
            ticket = await repo.get_ticket(ticket_id)
            result = await repo.close(ticket_id, closed_by=f"manager:{manager}")
            if ticket and (result or ticket.get("status") in ("open", "assigned")):
                await repo.append_message(
                    ticket_id,
                    author="system",
                    text=f"Диалог завершён менеджером {manager}.",
                )
                # Мягкое уведомление клиента о завершении диалога
                try:
                    await self._send_to_client(
                        int(ticket["chatId"]),
                        "Диалог с менеджером завершён. Если вопрос остался — напишите боту или запросите связь снова.",
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить клиента о закрытии: {e}")
            return RedirectResponse("/chats", status_code=303)
