"""
FastAPI сервис для обработки webhook-событий из МИС Renovatio. Принимает входящие вебхуки по URL /event отправляет уведомления по разным событиям
Путь: /server/start.py
"""
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, unquote
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from maxapi import Bot
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format
from dotenv import load_dotenv, find_dotenv
from starlette.requests import ClientDisconnect
from pydantic import BaseModel, Field
from libs.funcs import HelperFunction as hlp
from maxapi.types import RequestContactButton, CallbackButton
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.types.attachments.attachment import ButtonsPayload

from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi import Form
from bson import ObjectId

import html
from enum import Enum

from tools.keyboards import Keyboards


LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Файловый хендлер для логов запросов (ротация: 10МБ, 5 файлов)
request_file_handler = RotatingFileHandler(
    LOGS_DIR / "webhook_requests.log",
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)

request_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
request_logger = logging.getLogger('webhook_requests')
request_logger.setLevel(logging.INFO)
request_logger.addHandler(request_file_handler)
request_logger.propagate = False  # Не дублировать в общий лог

################################################
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

app = FastAPI(
    title="Renovatio Webhook Handler",
    description="Сервис обработки событий из МИС Renovatio",
    version="1.0.1"
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

mongo_client: Optional[AsyncIOMotorClient] = None
collection = None
collection_sender = None
max_bot: Optional[Bot] = None
collection_newsletters = None 
collection_newsletters_logs: Optional[Any] = None

class NewsletterStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


def is_valid_object_id(value: str) -> bool:
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def normalize_newsletter(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["_id"] = str(doc["_id"])
    doc.setdefault("name", "")
    doc.setdefault("text", "")
    doc.setdefault("status", NewsletterStatus.draft.value)
    doc.setdefault("attempt", 0)
    doc.setdefault("sentCount", 0)
    doc.setdefault("errorCount", 0)
    doc.setdefault("createdAt", datetime.now())
    return doc


def render_newsletter_text(text: str) -> str:
    """
    Экранируем HTML и переводим переносы строк в <br>.
    Если потом захочешь полноценные HTML-шаблоны, можно сделать отдельный Jinja-шаблон письма.
    """
    return html.escape(text or "").replace("\n", "<br>")

class NewsletterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)

class CallbackAction(CallbackPayload, prefix='visits'):
    action: str


@app.on_event("startup")
async def startup_event():
    global mongo_client, collection, max_bot, collection_sender, collection_newsletters, collection_newsletters_logs

    mongo_uri = os.getenv("MONGO_URI", "")
    db_name = os.getenv("DB_NAME", "spa_max")

    collection_name = os.getenv("COLLECTION_NAME", "users")
    collection_sender_name = os.getenv("COLLECTION_SENDER", "sender")
    collection_newsletters_name = os.getenv("COLLECTION_NEWSLETTERS", "newsletters")
    collection_newsletters_logs_name = os.getenv("COLLECTION_NEWSLETTERS_LOGS", "newsletters_logs")

    mongo_client = AsyncIOMotorClient(mongo_uri)
    db = mongo_client[db_name]

    collection = db[collection_name]
    collection_sender = db[collection_sender_name]
    collection_newsletters = db[collection_newsletters_name]
    collection_newsletters_logs = db[collection_newsletters_logs_name]

    try:
        await mongo_client.admin.command("ping")
        logger.info(f"✅ Подключение к MongoDB успешно: {mongo_uri}")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к MongoDB: {e}")
        raise

    bot_token = os.getenv("MAX_BOT_TOKEN")
    if not bot_token:
        raise ValueError("MAX_BOT_TOKEN is required in .env")

    max_bot = Bot(token=bot_token)

    # Индекс для защиты от дублей отправки в рамках одной попытки рассылки
    try:
        await collection_newsletters_logs.create_index(
            [("newsletterId", 1), ("attempt", 1), ("chatId", 1)],
            unique=True
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось создать индекс newsletter_logs: {e}")

    # Если сервис перезапустился во время рассылки, помечаем такие рассылки как failed
    try:
        await collection_newsletters.update_many(
            {"status": {"$in": ["queued", "running"]}},
            {
                "$set": {
                    "status": "failed",
                    "error": "Сервис перезапускался во время рассылки",
                    "updatedAt": datetime.now(),
                    "finishedAt": datetime.now(),
                }
            }
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось сбросить зависшие рассылки: {e}")

    logger.info("✅ Бот MAX инициализирован")
    logger.info("🚀 Webhook сервис запущен")

@app.on_event("shutdown")
async def shutdown_event():
    if mongo_client:
        mongo_client.close()
        logger.info("🔌 MongoDB соединение закрыто")
    if max_bot and hasattr(max_bot, 'session') and max_bot.session:
        await max_bot.session.close()
        logger.info("🔌 Сессия бота MAX закрыта")

async def run_newsletter(newsletter_id: str, attempt: int) -> None:
    """
    Фоновая отправка рассылки.
    attempt нужен, чтобы одну и ту же рассылку можно было запускать повторно,
    но в рамках одной попытки не слать дубли.
    """
    if collection_newsletters is None or collection is None or max_bot is None or collection_newsletters_logs is None:
        logger.error("❌ Не инициализированы коллекции или бот для рассылки")
        return

    try:
        oid = ObjectId(newsletter_id)
    except Exception:
        logger.error(f"❌ Некорректный newsletter_id: {newsletter_id}")
        return

    try:
        # Фиксируем, что рассылка началась, и защищаемся от параллельного запуска
        update_result = await collection_newsletters.update_one(
            {
                "_id": oid,
                "attempt": attempt,
                "status": {"$nin": [NewsletterStatus.running.value]},
            },
            {
                "$set": {
                    "status": NewsletterStatus.running.value,
                    "startedAt": datetime.now(),
                    "updatedAt": datetime.now(),
                },
                "$unset": {
                    "finishedAt": "",
                    "error": "",
                },
            }
        )

        if update_result.modified_count == 0:
            logger.info(f"⏭️ Рассылка {newsletter_id} уже запускается или не найдена")
            return

        newsletter = await collection_newsletters.find_one({"_id": oid})
        if not newsletter:
            logger.warning(f"⚠️ Рассылка {newsletter_id} не найдена")
            return

        message_text = newsletter.get("text", "")
        message_name = render_newsletter_text(newsletter.get("name", ""))

        sent = 0
        errors = 0
        processed = 0

        async for user in collection.find({"chatId": {"$exists": True}}):
            chat_id = user.get("chatId")
            user_name = user.get("name", "")
            if not chat_id:
                continue

            log_filter = {
                "newsletterId": newsletter_id,
                "attempt": attempt,
                "chatId": chat_id,
            }

            try:
                already_sent = await collection_newsletters_logs.find_one({
                    **log_filter,
                    "sent": True
                })

                if already_sent:
                    continue

                
                if "#" in message_text:
                    result = message_text.split("#")
                    message_text = ""
                    for str in result:
                        message_text += str + "\n"

                text = as_html(Heading(message_name)+"\n\n")
                text += message_text
                if "{name}" in text:
                    text = text.replace("{name}", user_name)

                attachments = Keyboards.menu_button()

                await max_bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    format=Format.HTML,
                    attachments=[attachments]
                )

                await collection_newsletters_logs.update_one(
                    log_filter,
                    {
                        "$set": {
                            "sent": True,
                            "date": datetime.now(),
                            "error": None,
                        }
                    },
                    upsert=True
                )

                sent += 1

            except Exception as e:
                errors += 1

                try:
                    await collection_newsletters_logs.update_one(
                        log_filter,
                        {
                            "$set": {
                                "sent": False,
                                "date": datetime.now(),
                                "error": str(e),
                            }
                        },
                        upsert=True
                    )
                except Exception as log_error:
                    logger.error(f"❌ Не удалось сохранить ошибку рассылки: {log_error}")

            processed += 1

            if processed % 10 == 0:
                await collection_newsletters.update_one(
                    {"_id": oid},
                    {
                        "$set": {
                            "sentCount": sent,
                            "errorCount": errors,
                            "updatedAt": datetime.now(),
                        }
                    }
                )

            # Небольшая защита от rate limit
            await asyncio.sleep(0.05)

        await collection_newsletters.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": NewsletterStatus.completed.value,
                    "sentCount": sent,
                    "errorCount": errors,
                    "finishedAt": datetime.now(),
                    "updatedAt": datetime.now(),
                },
                "$unset": {
                    "error": ""
                }
            }
        )

        logger.info(f"✅ Рассылка {newsletter_id} завершена: sent={sent}, errors={errors}")

    except Exception as e:
        logger.error(f"❌ Ошибка рассылки {newsletter_id}: {e}", exc_info=True)

        try:
            await collection_newsletters.update_one(
                {"_id": ObjectId(newsletter_id)},
                {
                    "$set": {
                        "status": NewsletterStatus.failed.value,
                        "error": str(e),
                        "finishedAt": datetime.now(),
                        "updatedAt": datetime.now(),
                    }
                }
            )
        except Exception:
            pass

@app.get("/")
async def root():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/newsletters", response_class=HTMLResponse)
async def newsletters_list(request: Request):
    if collection_newsletters is None:
        raise HTTPException(status_code=503, detail="MongoDB not initialized")

    items = []
    async for doc in collection_newsletters.find().sort("createdAt", -1).limit(200):
        items.append(normalize_newsletter(doc))

    has_active = any(
        item.get("status") in [NewsletterStatus.queued.value, NewsletterStatus.running.value]
        for item in items
    )

    return templates.TemplateResponse(
        request=request,
        name="newsletters/list.html",
        context={
            "items": items,
            "has_active": has_active,
        }
    )

@app.get("/health")
async def health_check():
    health = {"status": "ok", "checks": {}}
    try:
        await mongo_client.admin.command('ping')
        health["checks"]["mongodb"] = "ok"
    except Exception as e:
        health["checks"]["mongodb"] = f"error: {e}"
        health["status"] = "degraded"
        
    if max_bot:
        health["checks"]["max_bot"] = "initialized"
        
    return health

@app.get("/newsletters/new", response_class=HTMLResponse)
async def newsletter_new(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="newsletters/form.html",
        context={
            "mode": "create",
            "newsletter": None,
            "id": None,
        }
    )

@app.post("/newsletters")
async def newsletter_create(
    name: str = Form(...),
    text: str = Form(...)
):
    if collection_newsletters is None:
        raise HTTPException(status_code=503, detail="MongoDB not initialized")

    if not name.strip() or not text.strip():
        raise HTTPException(status_code=400, detail="Название и текст обязательны")

    doc = {
        "name": name.strip(),
        "text": text.strip(),
        "status": NewsletterStatus.draft.value,
        "attempt": 0,
        "sentCount": 0,
        "errorCount": 0,
        "createdAt": datetime.now(),
        "updatedAt": datetime.now(),
    }

    await collection_newsletters.insert_one(doc)

    return RedirectResponse("/newsletters", status_code=303)

@app.post("/newsletters/{newsletter_id}")
async def newsletter_update(
    newsletter_id: str,
    name: str = Form(...),
    text: str = Form(...)
):
    if collection_newsletters is None:
        raise HTTPException(status_code=503, detail="MongoDB not initialized")

    if not is_valid_object_id(newsletter_id):
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if not name.strip() or not text.strip():
        raise HTTPException(status_code=400, detail="Название и текст обязательны")

    doc = await collection_newsletters.find_one({"_id": ObjectId(newsletter_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if doc.get("status") in [NewsletterStatus.queued.value, NewsletterStatus.running.value]:
        raise HTTPException(
            status_code=409,
            detail="Нельзя редактировать рассылку, которая уже в очереди или отправляется"
        )

    await collection_newsletters.update_one(
        {"_id": ObjectId(newsletter_id)},
        {
            "$set": {
                "name": name.strip(),
                "text": text.strip(),
                "status": NewsletterStatus.draft.value,
                "updatedAt": datetime.now(),
            }
        }
    )

    return RedirectResponse("/newsletters", status_code=303)

@app.post("/newsletters/{newsletter_id}/delete")
async def newsletter_delete(newsletter_id: str):
    if collection_newsletters is None:
        raise HTTPException(status_code=503, detail="MongoDB not initialized")

    if not is_valid_object_id(newsletter_id):
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    doc = await collection_newsletters.find_one({"_id": ObjectId(newsletter_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if doc.get("status") in [NewsletterStatus.queued.value, NewsletterStatus.running.value]:
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить рассылку, которая уже в очереди или отправляется"
        )

    await collection_newsletters.delete_one({"_id": ObjectId(newsletter_id)})

    return RedirectResponse("/newsletters", status_code=303)

@app.get("/newsletters/{newsletter_id}/edit", response_class=HTMLResponse)
async def newsletter_edit(request: Request, newsletter_id: str):
    if collection_newsletters is None:
        raise HTTPException(status_code=503, detail="MongoDB not initialized")

    if not is_valid_object_id(newsletter_id):
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    doc = await collection_newsletters.find_one({"_id": ObjectId(newsletter_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    return templates.TemplateResponse(
        request=request,
        name="newsletters/form.html",
        context={
            "mode": "edit",
            "newsletter": normalize_newsletter(doc),
            "id": newsletter_id,
        }
    )

@app.post("/newsletters/{newsletter_id}/send")
async def newsletter_send(newsletter_id: str, background_tasks: BackgroundTasks):
    if collection_newsletters is None:
        raise HTTPException(status_code=503, detail="MongoDB not initialized")

    if not is_valid_object_id(newsletter_id):
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    doc = await collection_newsletters.find_one({"_id": ObjectId(newsletter_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if doc.get("status") in [NewsletterStatus.queued.value, NewsletterStatus.running.value]:
        raise HTTPException(
            status_code=409,
            detail="Рассылка уже в очереди или отправляется"
        )

    new_attempt = int(doc.get("attempt", 0)) + 1

    await collection_newsletters.update_one(
        {"_id": ObjectId(newsletter_id)},
        {
            "$set": {
                "status": NewsletterStatus.queued.value,
                "attempt": new_attempt,
                "sentCount": 0,
                "errorCount": 0,
                "updatedAt": datetime.now(),
            },
            "$unset": {
                "startedAt": "",
                "finishedAt": "",
                "error": "",
            }
        }
    )

    background_tasks.add_task(run_newsletter, newsletter_id, new_attempt)

    return RedirectResponse("/newsletters", status_code=303)

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", 8000))
    logger.info(f"🔧 Запуск сервера на {host}:{port}")
    uvicorn.run(
        "start:app",
        host=host,
        port=port,
        reload=os.getenv("ENV", "production") != "production",
        log_level="info"
    )
