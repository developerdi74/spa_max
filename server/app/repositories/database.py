"""
Репозитории для работы с MongoDB.
Инкапсуляция логики доступа к данным.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, AsyncGenerator
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from ..models.newsletter import NewsletterDocument, NewsletterLog, NewsletterStatus,NewsletterUpdate
from ..models.share import ShareDocument, ShareUpdate as ShareUpdateModel
from ..config.settings import Settings

logger = logging.getLogger(__name__)


class BaseRepository:
    """Базовый класс репозитория."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db


class NewsletterRepository(BaseRepository):
    """Репозиторий для работы с рассылками."""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        super().__init__(db)
        self.collection: AsyncIOMotorCollection = db[collection_name]
    
    async def create_index(self) -> None:
        """Создание индексов."""
        try:
            await self.collection.create_index([("createdAt", -1)])
            logger.info("✅ Индексы коллекции newsletters созданы")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать индексы: {e}")
    
    async def get_all(self, limit: int = 200) -> List[NewsletterDocument]:
        """Получение всех рассылок с сортировкой."""
        items = []
        async for doc in self.collection.find().sort("createdAt", -1).limit(limit):
            items.append(NewsletterDocument.from_mongo(doc))
        return items
    
    async def get_by_id(self, newsletter_id: str) -> Optional[NewsletterDocument]:
        """Получение рассылки по ID."""
        try:
            oid = ObjectId(newsletter_id)
            doc = await self.collection.find_one({"_id": oid})
            if doc:
                return NewsletterDocument.from_mongo(doc)
        except Exception as e:
            logger.error(f"❌ Ошибка получения рассылки {newsletter_id}: {e}")
        return None
    
    async def create(self, newsletter: NewsletterDocument) -> NewsletterDocument:
        """Создание новой рассылки."""
        doc = newsletter.to_mongo()
        doc["createdAt"] = datetime.now()
        doc["updatedAt"] = datetime.now()
        result = await self.collection.insert_one(doc)
        newsletter.id = str(result.inserted_id)
        return newsletter
    
    async def update(self, newsletter_id: str, newsletter: NewsletterUpdate) -> bool:
        """Обновление рассылки."""
        try:
            oid = ObjectId(newsletter_id)
            update_data = newsletter.dict()
            update_data["updatedAt"] = datetime.now()
            
            result = await self.collection.update_one(
                {"_id": oid},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка обновления рассылки {newsletter_id}: {e}")
            return False
    
    async def delete(self, newsletter_id: str) -> bool:
        """Удаление рассылки."""
        try:
            oid = ObjectId(newsletter_id)
            result = await self.collection.delete_one({"_id": oid})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка удаления рассылки {newsletter_id}: {e}")
            return False
    
    async def mark_as_queued(self, newsletter_id: str, new_attempt: int) -> bool:
        """Пометка рассылки как queued."""
        try:
            oid = ObjectId(newsletter_id)
            result = await self.collection.update_one(
                {"_id": oid},
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
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса рассылки {newsletter_id}: {e}")
            return False
    
    async def mark_as_running(self, newsletter_id: str, attempt: int) -> bool:
        """Пометка рассылки как running с защитой от параллельных запусков."""
        try:
            oid = ObjectId(newsletter_id)
            result = await self.collection.update_one(
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
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса рассылки {newsletter_id}: {e}")
            return False
    
    async def update_progress(
        self,
        newsletter_id: str,
        sent_count: int,
        error_count: int
    ) -> None:
        """Обновление прогресса рассылки."""
        try:
            oid = ObjectId(newsletter_id)
            await self.collection.update_one(
                {"_id": oid},
                {
                    "$set": {
                        "sentCount": sent_count,
                        "errorCount": error_count,
                        "updatedAt": datetime.now(),
                    }
                }
            )
        except Exception as e:
            logger.error(f"❌ Ошибка обновления прогресса рассылки: {e}")
    
    async def complete(self, newsletter_id: str, sent_count: int, error_count: int) -> None:
        """Завершение рассылки успешно."""
        try:
            oid = ObjectId(newsletter_id)
            await self.collection.update_one(
                {"_id": oid},
                {
                    "$set": {
                        "status": NewsletterStatus.completed.value,
                        "sentCount": sent_count,
                        "errorCount": error_count,
                        "finishedAt": datetime.now(),
                        "updatedAt": datetime.now(),
                    },
                    "$unset": {"error": ""}
                }
            )
            logger.info(f"✅ Рассылка {newsletter_id} завершена: sent={sent_count}, errors={error_count}")
        except Exception as e:
            logger.error(f"❌ Ошибка завершения рассылки {newsletter_id}: {e}")
    
    async def fail(self, newsletter_id: str, error: str) -> None:
        """Пометка рассылки как failed."""
        try:
            oid = ObjectId(newsletter_id)
            await self.collection.update_one(
                {"_id": oid},
                {
                    "$set": {
                        "status": NewsletterStatus.failed.value,
                        "error": error,
                        "finishedAt": datetime.now(),
                        "updatedAt": datetime.now(),
                    }
                }
            )
        except Exception as e:
            logger.error(f"❌ Ошибка пометки рассылки как failed: {e}")
    
    async def reset_stuck_newsletters(self) -> None:
        """Сброс зависших рассылок при перезапуске сервиса."""
        try:
            result = await self.collection.update_many(
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
            if result.modified_count > 0:
                logger.info(f"🔄 Сброшено {result.modified_count} зависших рассылок")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сбросить зависшие рассылки: {e}")
    
    async def has_active_newsletters(self) -> bool:
        """Проверка наличия активных рассылок."""
        count = await self.collection.count_documents(
            {"status": {"$in": ["queued", "running"]}}
        )
        return count > 0


class NewsletterLogRepository(BaseRepository):
    """Репозиторий для работы с логами рассылок."""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        super().__init__(db)
        self.collection: AsyncIOMotorCollection = db[collection_name]
    
    async def create_index(self) -> None:
        """Создание уникального индекса для защиты от дублей."""
        try:
            await self.collection.create_index(
                [("newsletterId", 1), ("attempt", 1), ("chatId", 1)],
                unique=True
            )
            logger.info("✅ Индексы коллекции newsletters_logs созданы")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать индекс newsletter_logs: {e}")
    
    async def log_send(
        self,
        newsletter_id: str,
        attempt: int,
        chat_id: str,
        sent: bool,
        error: Optional[str] = None
    ) -> None:
        """Логирование отправки сообщения."""
        log_entry = {
            "newsletterId": newsletter_id,
            "attempt": attempt,
            "chatId": chat_id,
            "sent": sent,
            "date": datetime.now(),
            "error": error,
        }
        
        try:
            await self.collection.update_one(
                {
                    "newsletterId": newsletter_id,
                    "attempt": attempt,
                    "chatId": chat_id,
                },
                {"$set": log_entry},
                upsert=True
            )
        except Exception as e:
            logger.error(f"❌ Ошибка логирования отправки: {e}")
    
    async def already_sent(
        self,
        newsletter_id: str,
        attempt: int,
        chat_id: str
    ) -> bool:
        """Проверка, было ли уже отправлено сообщение."""
        doc = await self.collection.find_one({
            "newsletterId": newsletter_id,
            "attempt": attempt,
            "chatId": chat_id,
            "sent": True
        })
        return doc is not None


class ShareRepository(BaseRepository):
    """Репозиторий для работы с акциями."""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        super().__init__(db)
        self.collection: AsyncIOMotorCollection = db[collection_name]
    
    async def create_index(self) -> None:
        """Создание индексов."""
        try:
            await self.collection.create_index([("createdAt", -1)])
            logger.info("✅ Индексы коллекции shares созданы")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать индексы: {e}")
    
    async def get_all(self, limit: int = 200) -> List[ShareDocument]:
        """Получение всех акций с сортировкой."""
        items = []
        async for doc in self.collection.find().sort("createdAt", -1).limit(limit):
            items.append(ShareDocument.from_mongo(doc))
        return items
    
    async def get_by_id(self, share_id: str) -> Optional[ShareDocument]:
        """Получение акции по ID."""
        try:
            oid = ObjectId(share_id)
            doc = await self.collection.find_one({"_id": oid})
            if doc:
                return ShareDocument.from_mongo(doc)
        except Exception as e:
            logger.error(f"❌ Ошибка получения акции {share_id}: {e}")
        return None
    
    async def create(self, share: ShareDocument) -> ShareDocument:
        """Создание новой акции."""
        doc = share.to_mongo()
        doc["createdAt"] = datetime.now()
        doc["updatedAt"] = datetime.now()
        result = await self.collection.insert_one(doc)
        share.id = str(result.inserted_id)
        return share
    
    async def update(self, share_id: str, share: ShareUpdateModel) -> bool:
        """Обновление акции."""
        try:
            oid = ObjectId(share_id)
            update_data = share.dict()
            update_data["updatedAt"] = datetime.now()
            
            result = await self.collection.update_one(
                {"_id": oid},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка обновления акции {share_id}: {e}")
            return False
    
    async def delete(self, share_id: str) -> bool:
        """Удаление акции."""
        try:
            oid = ObjectId(share_id)
            result = await self.collection.delete_one({"_id": oid})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"❌ Ошибка удаления акции {share_id}: {e}")
            return False


class UserRepository(BaseRepository):
    """Репозиторий для работы с пользователями."""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        super().__init__(db)
        self.collection: AsyncIOMotorCollection = db[collection_name]
    
    async def get_users_with_chat_ids(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Получение всех пользователей с chatId."""
        async for user in self.collection.find({"chatId": {"$exists": True}}):
            yield user


class DatabaseManager:
    """Менеджер подключения к базе данных."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        
        # Репозитории
        self.newsletters: Optional[NewsletterRepository] = None
        self.newsletter_logs: Optional[NewsletterLogRepository] = None
        self.users: Optional[UserRepository] = None
        self.shares: Optional[ShareRepository] = None
    
    async def connect(self) -> None:
        """Подключение к MongoDB."""
        self.client = AsyncIOMotorClient(self.settings.MONGO_URI)
        self.db = self.client[self.settings.DB_NAME]
        
        # Инициализация репозиториев
        self.newsletters = NewsletterRepository(
            self.db,
            self.settings.COLLECTION_NEWSLETTERS
        )
        self.newsletter_logs = NewsletterLogRepository(
            self.db,
            self.settings.COLLECTION_NEWSLETTERS_LOGS
        )
        self.users = UserRepository(
            self.db,
            self.settings.COLLECTION_USERS
        )
        self.shares = ShareRepository(
            self.db,
            "shares"
        )
        
        # Создание индексов
        await self.newsletters.create_index()
        await self.newsletter_logs.create_index()
        await self.shares.create_index()
        
        # Проверка подключения
        try:
            await self.client.admin.command("ping")
            logger.info(f"✅ Подключение к MongoDB успешно: {self.settings.MONGO_URI}")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к MongoDB: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Отключение от MongoDB."""
        if self.client:
            self.client.close()
            logger.info("🔌 MongoDB соединение закрыто")
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья базы данных."""
        try:
            await self.client.admin.command('ping')
            return {"mongodb": "ok"}
        except Exception as e:
            return {"mongodb": f"error: {e}"}
