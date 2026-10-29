"""
Хендлер живого чата «менеджер — подписчик».

Логика:
  • Кнопка «Связаться с менеджером» (или AI-интент operator) создаёт тикет
    в коллекции support_tickets и уведомляет чаты менеджеров (MANAGER_CHAT_IDS).
  • Пока у чата активный тикет (open/assigned), все текстовые сообщения
    клиента перехватываются этим хендлером (регистрация идёт раньше
    AiAnswerHandler/DefaultMessageHandler) и кладутся в историю тикета.
  • Команда /cancel или кнопка отмены закрывает тикет — клиент снова у бота.
  • Ответы менеджеров приходят через админ-панель (она пишет в тот же тикет
    и отправляет сообщение клиенту тем же токеном бота).
"""

import logging
from typing import Optional

from maxapi import Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback
from maxapi.utils.formatting import Bold, Heading, as_html
from maxapi.enums.format import Format

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.payloads import ChatActionPayload
from listener.storage import MongoStorage
from listener.services.salon1c_service import Salon1CService
from listener.utils import get_chat_id
from libs.chat_state import ACTIVE_STATUSES, ChatSettings


class ManagerChatHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, bot, config, salon1c_service: Salon1CService):
        self._storage = storage
        self._bot = bot
        self._salon_service = salon1c_service
        self._settings = ChatSettings.from_env()

    # ------------------------------------------------------------------
    def register(self, dp: Dispatcher) -> None:
        # Кнопки управления диалогом
        dp.message_callback(ChatActionPayload.filter(F.action == "open"))(self.open_chat)
        dp.message_callback(ChatActionPayload.filter(F.action == "cancel"))(self.cancel_chat)
        dp.message_callback(ChatActionPayload.filter(F.action == "menu"))(self.to_main_menu)
        # Перехват сообщений клиента ДО ai/default хендлеров
        dp.message_created()(self.route_message)

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    async def _notify_managers(self, text: str) -> None:
        """Уведомление менеджеров (их chatId из env MANAGER_CHAT_IDS)."""
        for manager_chat_id in self._settings.manager_chat_ids:
            try:
                await self._bot.send_message(chat_id=manager_chat_id, text=text)
            except Exception as e:
                logging.error(f"Не удалось уведомить менеджера {manager_chat_id}: {e}")

    async def _user_info(self, chat_id: int) -> dict:
        record = await self._storage.get_record_by_chat_id(chat_id, collection_name="users") or {}
        return {
            "name": record.get("name", ""),
            "phoneNumber": record.get("phoneNumber", ""),
        }

    async def _active_ticket(self, chat_id: int):
        return await self._storage.get_active_ticket(chat_id)

    # ------------------------------------------------------------------
    # Создание обращения
    # ------------------------------------------------------------------
    async def open_chat(self, event: MessageCallback, payload: ChatActionPayload) -> None:
        chat_id = get_chat_id(event)
        if not chat_id:
            return
        await self._create_ticket_and_answer(event, chat_id, reason="Клиент запросил связь с менеджером")

    async def escalate_from_ai(self, event: MessageCreated, reason: str = "") -> bool:
        """Вызывается AiAnswerHandler при интенте operator: открывает тикет."""
        chat_id = get_chat_id(event)
        if not chat_id:
            return False
        ticket, created = await self._storage.create_or_reopen_ticket(
            chat_id=chat_id,
            user_info=await self._user_info(chat_id),
            reason=reason or "Эскалация из AI-диалога",
            source="ai",
        )
        if created and ticket:
            await self._notify_managers(
                f"🆕 Новое обращение (AI)\nКлиент: {ticket['userInfo'].get('name') or '—'}\n"
                f"Телефон: {ticket['userInfo'].get('phoneNumber') or '—'}\n"
                f"Причина: {reason or 'оператор'}\nОтветьте в админ-панели: /chats/{ticket['_id']}"
            )
        return True

    async def _create_ticket_and_answer(
        self, event: MessageCallback, chat_id: int, reason: str
    ) -> None:
        ticket, created = await self._storage.create_or_reopen_ticket(
            chat_id=chat_id,
            user_info=await self._user_info(chat_id),
            reason=reason,
            source="button",
        )
        if not created and ticket:
            await event.answer(
                new_text=as_html(Heading("💬 Вы уже в диалоге с менеджером!")),
                attachments=[Keyboards.chat_connecting()],
                format=Format.HTML,
            )
            return

        if ticket:
            await self._notify_managers(
                f"🆕 Новое обращение\nКлиент: {ticket['userInfo'].get('name') or '—'}\n"
                f"Телефон: {ticket['userInfo'].get('phoneNumber') or '—'}\n"
                f"Причина: {reason}\nОтветьте в админ-панели: /chats/{ticket['_id']}"
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

    # ------------------------------------------------------------------
    # Маршрутизация входящих сообщений клиента
    # ------------------------------------------------------------------
    async def route_message(self, event: MessageCreated) -> None:
        text = (event.message.body.text or "").strip()
        if not text:
            return

        chat_id = get_chat_id(event)
        if not chat_id:
            return

        ticket = await self._active_ticket(chat_id)
        if not ticket:
            # Тикета нет — отдаём сообщение дальше (AI/дефолтный хендлеры)
            raise NextHandler

        # Отмена диалога текстом
        if text.lower() in ("/cancel", "отмена", "отменить"):
            await self._close_and_notify(event, chat_id, ticket)
            return

        await self._storage.append_ticket_message(
            ticket["_id"], author="client", text=text
        )
        await self._notify_managers(
            f"💬 Сообщение от клиента (чат {chat_id}):\n{text[:500]}\n"
            f"Ответ: /chats/{ticket['_id']}"
        )
        await event.message.answer(
            text="✅ Сообщение передано менеджеру. Ожидайте ответа.",
            attachments=[Keyboards.chat_connecting()],
        )

    # ------------------------------------------------------------------
    # Закрытие / возврат в меню
    # ------------------------------------------------------------------
    async def cancel_chat(self, event: MessageCallback, payload: ChatActionPayload) -> None:
        chat_id = get_chat_id(event)
        if not chat_id:
            return
        ticket = await self._active_ticket(chat_id)
        if not ticket:
            await event.answer(new_text="Активного диалога с менеджером нет.", attachments=[Keyboards.main_menu()])
            return
        await self._storage.close_ticket(ticket["_id"], closed_by="client")
        await self._notify_managers(f"❌ Клиент {chat_id} завершил диалог сам.")
        await event.answer(
            new_text=as_html(Heading("Диалог с менеджером завершён") + "\nВозвращаю вас в меню."),
            attachments=[Keyboards.main_menu()],
            format=Format.HTML,
        )

    async def to_main_menu(self, event: MessageCallback, payload: ChatActionPayload) -> None:
        from listener.payloads import CallbackAction
        # Просто показываем главное меню, не трогая тикет
        await event.answer(
            new_text=as_html(Heading("🌸 Главное меню")),
            attachments=[Keyboards.main_menu()],
            format=Format.HTML,
        )

    async def _close_and_notify(self, event: MessageCreated, chat_id: int, ticket) -> None:
        await self._storage.close_ticket(ticket["_id"], closed_by="client")
        await self._notify_managers(f"❌ Клиент {chat_id} завершил диалог (/cancel).")
        await event.message.answer(
            text="Диалог с менеджером завершён. Возвращаю вас в меню.",
            attachments=[Keyboards.main_menu()],
        )


# Экспортируем статусы для внешних проверок
__all__ = ["ManagerChatHandler", "ACTIVE_STATUSES"]
