"""
Роутер живого чата «менеджер — подписчик» (приоритетная ветка).

maxapi не поддерживает «next handler»: диспетчер выполняет ПЕРВЫЙ
подходящий обработчик и останавливается. Поэтому реализация такая:

  1. В конструкторе Dispatcher передаётся кастомный ``custom_filter`` —
     функция :func:`manager_chat_gate` (см. listener/app.py). Она выполняется
     для каждого события ДО подбора хендлеров и умеет полностью «съесть»
     событие (вернуть ``{"_stop": True}``) — тогда ни один обычный хендлер
     (включая AiAnswerHandler) не вызывается. Так сообщения клиента с
     активным тикетом гарантированно не попадают в AI-ответчик.

  2. Сам роутер (регистрируется РАНЬШЕ обычных хендлеров через
     ``dp.include_routers``) обрабатывает кнопки диалога
     (``chat:open`` / ``chat:cancel`` / ``chat:menu``), а также принимает
     сообщения клиентов, которые гейт передал дальше (например, при
     временной недоступности MongoDB — чтобы бот продолжил отвечать).

Логика перехвата:
  • Активный тикет (open/assigned) + непустой текст без контакта →
    сообщение пишется в историю тикета, менеджеры получают уведомление,
    клиенту — подтверждение; событие остановлено.
  • Ошибки инфраструктуры (Mongo недоступна) → событие отдаётся обычным
    хендлерам (бот работает как раньше).
"""

import asyncio
import logging
from typing import Any, Optional

from maxapi import Bot, Dispatcher, F, Router
from maxapi.filters.middleware import BaseMiddleware, HandlerCallable
from maxapi.types import MessageCreated, MessageCallback
from maxapi.utils.formatting import Bold, Heading, as_html
from maxapi.enums.format import Format
from maxapi.enums.update_type import UpdateType

from listener.keyboards import Keyboards
from listener.payloads import ChatActionPayload
from listener.storage import MongoStorage
from listener.utils import get_chat_id
from libs.chat_state import ACTIVE_STATUSES, ChatSettings

logger = logging.getLogger(__name__)


def _extract_text(event: MessageCreated) -> str:
    """Безопасно достаёт текст сообщения (attachment-ы могут быть None)."""
    try:
        message = getattr(event, "message", None)
        body = getattr(message, "body", None)
        return ((getattr(body, "text", None) or "").strip())
    except Exception:  # noqa: BLE001
        return ""


def _has_contact(event: MessageCreated) -> bool:
    """Сообщение содержит переданный контакт — его должен обрабатывать бот."""
    try:
        body = getattr(event.message, "body", None)
        for att in (getattr(body, "attachments", None) or []):
            content_type = getattr(getattr(att, "content", None), "type", None)
            if content_type is not None and str(content_type) == "contact":
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


class ManagerChatGate(BaseMiddleware):
    """Глобальная outer-middleware диспетчера: «гейт» живого чата.

    Выполняется для КАЖДОГО события раньше подбора хендлеров. Если у чата
    есть активный тикет и это текстовое сообщение клиента без контакта —
    перехватывает событие целиком (AiAnswerHandler и прочие хендлеры не
    вызываются). Иначе пропускает событие дальше как обычно.

    Любая внутренняя ошибка (недоступна Mongo и т.п.) — событие
    пропускается к обычным хендлерам, чтобы бот не «немел».
    """

    def __init__(self, router_owner: "ManagerChatRouter"):
        self._owner = router_owner

    async def __call__(self, handler: HandlerCallable, event, data: dict) -> Any:
        try:
            if await self._owner.try_intercept(event):
                return None  # событие полностью обработано, хендлеры не нужны
        except Exception as e:  # noqa: BLE001
            logger.error(f"ManagerChatGate: ошибка перехвата, отдаю событие боту: {e}", exc_info=True)
        return await handler(event, data)


class ManagerChatRouter:
    """Инкапсулирует приоритетную ветку обработки чатов с менеджером."""

    def __init__(self, storage: MongoStorage, bot: Bot, config: Any = None):
        self._storage = storage
        self._bot = bot
        self._config = config
        self._settings = ChatSettings.from_env()
        self.router = Router()
        self._setup()

    # ------------------------------------------------------------------
    def _setup(self) -> None:
        self.router.message_callback(ChatActionPayload.filter(F.action == "open"))(self.open_chat)
        self.router.message_callback(ChatActionPayload.filter(F.action == "cancel"))(self.cancel_chat)
        self.router.message_callback(ChatActionPayload.filter(F.action == "menu"))(self.to_main_menu)
        self.router.message_created()(self.route_message)

    def register(self, dp: Dispatcher) -> None:
        """Подключает роутер к диспетчеру (вызывается до остальных хендлеров)."""
        dp.include_routers(self.router)

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    async def _notify_managers(self, text: str) -> None:
        """Уведомление чатов менеджеров (chatId из env MANAGER_CHAT_IDS)."""
        if not self._settings.manager_chat_ids:
            logger.debug("MANAGER_CHAT_IDS не задан — уведомление менеджеров пропущено")
            return
        for manager_chat_id in self._settings.manager_chat_ids:
            try:
                await self._bot.send_message(chat_id=manager_chat_id, text=text)
            except Exception as e:  # noqa: BLE001
                logger.error(f"Не удалось уведомить менеджера {manager_chat_id}: {e}")

    async def _user_info(self, chat_id: int) -> dict:
        record = await self._storage.get_record_by_chat_id(chat_id, collection_name="users") or {}
        return {
            "name": record.get("name", "") or "",
            "phoneNumber": record.get("phoneNumber", "") or "",
        }

    async def _active_ticket(self, chat_id: int) -> Optional[dict]:
        return await self._storage.get_active_ticket(chat_id)

    @staticmethod
    def _ticket_url(ticket: dict) -> str:
        return f"/chats/{ticket['_id']}"

    # ------------------------------------------------------------------
    # Создание обращения
    # ------------------------------------------------------------------
    async def open_chat(self, event: MessageCallback, payload: ChatActionPayload) -> None:
        chat_id = get_chat_id(event)
        if not chat_id:
            return
        ticket, created = await self._storage.create_or_reopen_ticket(
            chat_id=chat_id,
            user_info=await self._user_info(chat_id),
            reason="Клиент запросил связь с менеджером",
            source="button",
        )

        if not created:
            if ticket:
                await self._notify_managers(
                    f"🔁 Клиент {chat_id} снова запросил менеджера.\n"
                    f"Ответьте в админ-панели: {self._ticket_url(ticket)}"
                )
            await event.answer(
                new_text=as_html(Heading("💬 Вы уже в диалоге с менеджером!")),
                attachments=[Keyboards.chat_connecting()],
                format=Format.HTML,
            )
            return

        if ticket:
            await self._notify_managers(
                f"🆕 Новое обращение\n"
                f"Клиент: {ticket['userInfo'].get('name') or '—'}\n"
                f"Телефон: {ticket['userInfo'].get('phoneNumber') or '—'}\n"
                f"ChatID: {chat_id}\n"
                f"Причина: {ticket.get('reason', '')}\n"
                f"Ответьте в админ-панели: {self._ticket_url(ticket)}"
            )

        await event.answer(
            new_text=as_html(
                Heading("💬 Соединяю с менеджером")
                + "\n\n"
                + "Опишите ваш вопрос обычным сообщением — оно дойдёт до сотрудника.\n"
                + Bold(f"Ожидаемое время ответа: до {self._settings.wait_timeout_min} мин.")
                + "\nОтменить — кнопка ниже."
            ),
            attachments=[Keyboards.chat_connecting()],
            format=Format.HTML,
        )

    async def escalate_from_ai(self, chat_id: int, reason: str = "") -> Optional[dict]:
        """Вызывается AiAnswerHandler при интенте `operator`: открывает тикет.

        Возвращает документ тикета (или None, если диалог уже активен).
        """
        ticket, created = await self._storage.create_or_reopen_ticket(
            chat_id=chat_id,
            user_info=await self._user_info(chat_id),
            reason=reason or "Эскалация из AI-диалога",
            source="ai",
        )
        if created and ticket:
            await self._notify_managers(
                f"🆕 Новое обращение (AI)\n"
                f"Клиент: {ticket['userInfo'].get('name') or '—'}\n"
                f"Телефон: {ticket['userInfo'].get('phoneNumber') or '—'}\n"
                f"ChatID: {chat_id}\n"
                f"Причина: {reason or 'оператор'}\n"
                f"Ответьте в админ-панели: {self._ticket_url(ticket)}"
            )
        return ticket

    # ------------------------------------------------------------------
    # Перехват сообщений клиента
    # ------------------------------------------------------------------
    async def route_message(self, event: MessageCreated) -> bool:
        """True — сообщение съедено (передано менеджеру), False — пусть работает бот."""
        chat_id = get_chat_id(event)
        if not chat_id:
            return False

        text = _extract_text(event)
        if not text or _has_contact(event):
            # Пустые/аттачмент-сообщения и передача контакта — зона обычных хендлеров
            return False

        ticket = await self._active_ticket(chat_id)
        if not ticket:
            return False

        # Отмена диалога текстом
        if text.lower() in ("/cancel", "отмена", "отменить"):
            await self._close_and_notify(chat_id, ticket, closed_by="client")
            await event.message.answer(
                text="Диалог с менеджером завершён. Возвращаю вас в меню.",
                attachments=[Keyboards.main_menu()],
            )
            return True

        await self._storage.append_ticket_message(ticket["_id"], author="client", text=text)
        await self._notify_managers(
            f"💬 Сообщение от клиента (чат {chat_id}):\n{text[:500]}\n"
            f"Ответ: {self._ticket_url(ticket)}"
        )
        await event.message.answer(
            text="✅ Сообщение передано менеджеру. Ожидайте ответа.",
            attachments=[Keyboards.chat_connecting()],
        )
        return True

    # ------------------------------------------------------------------
    # Закрытие / возврат в меню
    # ------------------------------------------------------------------
    async def cancel_chat(self, event: MessageCallback, payload: ChatActionPayload) -> None:
        chat_id = get_chat_id(event)
        if not chat_id:
            return
        ticket = await self._active_ticket(chat_id)
        if not ticket:
            await event.answer(
                new_text="Активного диалога с менеджером нет.",
                attachments=[Keyboards.main_menu()],
            )
            return
        await self._close_and_notify(chat_id, ticket, closed_by="client")
        await event.answer(
            new_text=as_html(Heading("Диалог с менеджером завершён") + "\nВозвращаю вас в меню."),
            attachments=[Keyboards.main_menu()],
            format=Format.HTML,
        )

    async def to_main_menu(self, event: MessageCallback, payload: ChatActionPayload) -> None:
        """Кнопка «Главное меню» внутри активного диалога: тикет НЕ закрываем."""
        await event.answer(
            new_text=as_html(Heading("🌸 Главное меню")),
            attachments=[Keyboards.main_menu()],
            format=Format.HTML,
        )

    async def _close_and_notify(self, chat_id: int, ticket: dict, *, closed_by: str) -> Optional[dict]:
        result = await self._storage.close_ticket(ticket["_id"], closed_by=closed_by)
        await self._notify_managers(f"❌ Клиент {chat_id} завершил диалог ({closed_by}).")
        return result


__all__ = ["ManagerChatRouter", "ACTIVE_STATUSES"]
