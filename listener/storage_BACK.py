import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection


class MongoStorage:
    def __init__(self, mongo_uri: str, db_name: str, collection_name: str):
        self._mongo_uri = mongo_uri
        self._db_name = db_name
        self._collection_name = collection_name
        self._client: AsyncIOMotorClient | None = None
        self._collection: AsyncIOMotorCollection | None = None

    @property
    def collection(self) -> AsyncIOMotorCollection:
        if self._collection is None:
            raise RuntimeError("MongoDB не инициализирован. Вызовите connect() перед использованием.")
        return self._collection

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(self._mongo_uri)
        self._collection = self._client[self._db_name][self._collection_name]

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._collection = None

    async def get_phone(self, chat_id: int) -> str | None:
        record = await self.collection.find_one({"chatId": chat_id})
        if not record:
            return None
        return record.get("phoneNumber") or None

    async def get_record_by_chat_id(self, chat_id: int) -> dict | None:
        return await self.collection.find_one({"chatId": chat_id})

    async def upsert_contact(
        self,
        *,
        user_id: int,
        chat_id: int,
        phone: str,
        full_name: str,
    ) -> None:
        update_data = {
            "userId": user_id,
            "chatId": chat_id,
            "name": full_name,
            "date": datetime.now(),
            "eventType": "add_contact",
        }

        existing_record = await self.collection.find_one({"phoneNumber": phone})

        if existing_record:
            result = await self.collection.update_one(
                {"phoneNumber": phone},
                {"$set": update_data},
            )
            logging.info(
                "Запись для номера %s обновлена. Изменено документов: %s",
                phone,
                result.modified_count,
            )
            return

        insert_data = {**update_data, "phoneNumber": phone}
        result = await self.collection.insert_one(insert_data)
        logging.info("Новая запись в MongoDB добавлена с ID: %s", result.inserted_id)

    async def insert_message(self, *, phone: int, message_client:str="", message_ai:str="") -> None:
        insert_data = {
            "phone": phone,
            "message_client": message_client,
            "message_ai": message_ai,
            "date": datetime.now(),
        }
        result = await self.collection.insert_one(insert_data)
        logging.info("Новая запись в MongoDB добавлена с ID: %s", result.inserted_id)