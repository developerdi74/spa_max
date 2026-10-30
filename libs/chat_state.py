"""
Общий модуль состояния чатов "клиент — менеджер" (тикетная система).

Используется сервисами:
    - listener (перехват сообщений клиента, эскалация, возврат к боту)
    - admin   (рабочее место менеджера: очередь, ответы, закрытие)
    - sender  (фоновые задачи: таймауты ожидания/бездействия)

Хранение: MongoDB, коллекция `support_tickets` (имя настраивается через env
COLLECTION_SUPPORT_TICKETS). Одно активное обращение (тикет) на один чат.

Статусы тикета:
    open     — создан, ждёт ответа менеджера
    assigned — взят менеджером в работу
    closed   — закрыт (менеджером, клиентом или по таймауту)
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Any, Dict

# Активные статусы, при которых сообщения клиента перехватываются у бота
ACTIVE_STATUSES = ("open", "assigned")

TICKET_COLLECTION = os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")


@dataclass(frozen=True)
class ChatSettings:
    """Настройки диалога с менеджером (из переменных окружения)."""
    manager_chat_ids: Tuple[int, ...]      # чаты менеджеров для уведомлений
    wait_timeout_min: int                  # сколько ждать менеджера, пока клиент у бота
    idle_close_min: int                    # бездействие клиента — автозакрытие тикета

    @classmethod
    def from_env(cls) -> "ChatSettings":
        raw = os.getenv("MANAGER_CHAT_IDS", "")
        chat_ids = tuple(
            int(x.strip()) for x in raw.replace(";", ",").split(",") if x.strip().lstrip("-").isdigit()
        )
        return cls(
            manager_chat_ids=chat_ids,
            wait_timeout_min=int(os.getenv("CHAT_WAIT_TIMEOUT_MIN", "30")),
            idle_close_min=int(os.getenv("CHAT_IDLE_CLOSE_MIN", "120")),
        )


def get_db(client, db_name: str = ""):
    """Возвращает базу данных из Motor-клиента."""
    name = db_name or os.getenv("DB_NAME", "")
    return client[name]


def tickets_collection(db):
    """Коллекция тикетов из объекта базы."""
    return db[TICKET_COLLECTION]


async def ensure_indexes(db) -> None:
    """Индексы для быстрой очереди и TTL-подчистки закрытых тикетов."""
    col = tickets_collection(db)
    await col.create_index([("status", 1), ("updatedAt", -1)], background=True)
    await col.create_index("chatId", background=True)
    # Храним закрытые тикеты (история) 90 дней
    await col.create_index(
        [("closedAt", 1)],
        partialFilterExpression={"status": "closed"},
        expireAfterSeconds=90 * 24 * 3600,
        background=True,
    )


async def get_active_ticket(col, chat_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает активный (open/assigned) тикет чата, если он есть."""
    return await col.find_one({"chatId": chat_id, "status": {"$in": list(ACTIVE_STATUSES)}})


async def create_or_reopen_ticket(
    col,
    *,
    chat_id: int,
    user_info: Optional[dict] = None,
    reason: str = "",
    source: str = "button",
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Создаёт тикет или заново открывает закрытый.

    Возвращает (ticket, created_new). Если тикет уже активен — (None, False).
    """
    now = datetime.now()
    active = await get_active_ticket(col, chat_id)
    if active:
        return None, False

    user_info = dict(user_info or {})
    last_message = {
        "author": "client",
        "text": reason or "Запрос связи с менеджером",
        "at": now,
    }

    existing = await col.find_one({"chatId": chat_id}, sort=[("createdAt", -1)])
    if existing and existing.get("status") == "closed":
        # Переиспользуем документ: история остаётся, статус сбрасывается
        update = {
            "status": "open",
            "assignedTo": None,
            "reason": reason,
            "source": source,
            "userInfo": user_info,
            "lastMessage": last_message,
            "clientLastActivity": now,
            "managerLastActivity": None,
            "closedAt": None,
            "reopenCount": existing.get("reopenCount", 0) + 1,
            "updatedAt": now,
        }
        await col.update_one({"_id": existing["_id"]}, {"$set": update})
        ticket = await col.find_one({"_id": existing["_id"]})
        return ticket, False

    ticket = {
        "chatId": chat_id,
        "status": "open",
        "assignedTo": None,
        "reason": reason,
        "source": source,
        "createdAt": now,
        "updatedAt": now,
        "clientLastActivity": now,
        "managerLastActivity": None,
        "closedAt": None,
        "reopenCount": 0,
        "userInfo": user_info,
        "history": [last_message],
        "lastMessage": last_message,
    }
    res = await col.insert_one(ticket)
    ticket["_id"] = res.inserted_id
    return ticket, True


async def append_message(
    col,
    ticket_id,
    *,
    author: str,
    text: str,
    manager: Optional[str] = None,
) -> None:
    """Добавляет сообщение в историю тикета и обновляет активность."""
    now = datetime.now()
    entry = {"author": author, "text": text, "at": now}
    if manager:
        entry["manager"] = manager

    update = {"$push": {"history": entry}}
    if author == "client":
        update["$set"] = {"clientLastActivity": now, "lastMessage": entry, "updatedAt": now}
    else:
        update["$set"] = {"managerLastActivity": now, "lastMessage": entry, "updatedAt": now}
    await col.update_one({"_id": ticket_id}, update)


async def close_ticket(col, ticket_id, *, closed_by: str) -> Optional[Dict[str, Any]]:
    """Закрывает тикет, возвращает его документ (или None, если уже закрыт)."""
    now = datetime.now()
    res = await col.update_one(
        {"_id": ticket_id, "status": {"$in": list(ACTIVE_STATUSES)}},
        {"$set": {"status": "closed", "closedAt": now, "closedBy": closed_by, "updatedAt": now}},
    )
    if res.modified_count == 0:
        return None
    return await col.find_one({"_id": ticket_id})


async def assign_ticket(col, ticket_id, *, manager: str) -> Optional[Dict[str, Any]]:
    """Берёт тикет в работу (open -> assigned). Повторный вызов идемпотентен."""
    now = datetime.now()
    await col.update_one(
        {"_id": ticket_id, "status": "open"},
        {"$set": {"status": "assigned", "assignedTo": manager, "updatedAt": now}},
    )
    return await col.find_one({"_id": ticket_id})


async def get_ticket(col, ticket_id):
    """Тикет по _id (ObjectId или строка)."""
    from bson import ObjectId
    try:
        oid = ObjectId(str(ticket_id))
    except Exception:
        return None
    return await col.find_one({"_id": oid})


def _serialize_ticket(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Готовит документ тикета к отдаче через json (без Motor-курсора)."""
    out = dict(doc)
    out["_id"] = str(out.get("_id", ""))
    history = []
    for m in out.get("history", []):
        h = dict(m)
        h["at"] = h.get("at") or None
        history.append(h)
    out["history"] = history
    lm = dict(out.get("lastMessage") or {})
    out["lastMessage"] = lm
    return out


async def list_tickets(
    col,
    *,
    statuses: Tuple[str, ...] = ACTIVE_STATUSES,
    limit: int = 200,
) -> list:
    """Список тикетов с фильтрацией по статусам и сортировкой по активности."""
    cursor = (
        col.find({"status": {"$in": list(statuses)}})
        .sort([("updatedAt", -1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize_ticket(d) for d in docs]


async def ticket_stats(col) -> Dict[str, int]:
    """Количество тикетов по статусам (для бейджа в меню админки)."""
    result = {s: 0 for s in ACTIVE_STATUSES + ("closed",)}
    async for doc in col.aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    ):
        result[doc["_id"]] = doc["count"]
    return result
