import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import List, Optional
from datetime import datetime, timedelta

class MongoStorage:
    def __init__(self, mongo_uri: str, db_name: str, default_collection_name: str):
        self._mongo_uri = mongo_uri
        self._db_name = db_name
        self._default_collection_name = default_collection_name
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None
        self._collections: dict[str, AsyncIOMotorCollection] = {}  # Кэш коллекций

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(
            self._mongo_uri,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=10,
        )
        self._db = self._client[self._db_name]
        await self._create_indexes()

    async def _create_indexes(self) -> None:
        """Создание индексов для оптимизации запросов."""
        if self._db is None:
            raise RuntimeError("MongoDB не инициализирован. Вызовите connect().")
        
        try:
            # Индексы для коллекции users
            users_collection = self._db["users"]
            await users_collection.create_index("chatId", unique=True, background=True)
            await users_collection.create_index("phoneNumber", unique=True, background=True)
            logging.info("Индексы для коллекции 'users' созданы")

            # Индексы для коллекции request_access
            request_access_collection = self._db["request_access"]
            await request_access_collection.create_index([("phone", 1), ("date", -1)], background=True)
            await request_access_collection.create_index("date", expireAfterSeconds=600, background=True)  # TTL 10 минут
            logging.info("Индексы для коллекции 'request_access' созданы")

            # Индексы для коллекции messages
            messages_collection = self._db["messages"]
            await messages_collection.create_index([("phone", 1), ("date", -1)], background=True)
            await messages_collection.create_index("date", expireAfterSeconds=2592000, background=True)  # TTL 30 дней
            logging.info("Индексы для коллекции 'messages' созданы")

            # Индексы для коллекции shares
            shares_collection = self._db["shares"]
            await shares_collection.create_index("active", background=True)
            logging.info("Индексы для коллекции 'shares' созданы")

            # Индексы для коллекции faqs
            faqs_collection = self._db["faqs"]
            await faqs_collection.create_index("active", background=True)
            logging.info("Индексы для коллекции 'faqs' созданы")

        except Exception as e:
            logging.error(f"Ошибка при создании индексов: {e}")
            raise

    def _get_collection(self, collection_name: str | None = None) -> AsyncIOMotorCollection:
        """Возвращает нужную коллекцию или дефолтную, если имя не передано.
        Использует кэширование для ускорения доступа."""
        if self._db is None:
            raise RuntimeError("MongoDB не инициализирован. Вызовите connect().")
        
        name = collection_name or self._default_collection_name
        
        # Кэшируем коллекцию для ускорения повторных обращений
        if name not in self._collections:
            self._collections[name] = self._db[name]
        
        return self._collections[name]


    # Пример изменения метода: добавляем опциональный параметр collection_name
    async def get_phone(self, chat_id: int, collection_name: str | None = None) -> str | None:        
        collection = self._get_collection(collection_name = "users")
        # Убраны лишние пробелы в ключах (см. P.S.)
        record = await collection.find_one({"chatId": chat_id}) 
        return record.get("phoneNumber") if record else None

    async def get_record_by_chat_id(self, chat_id: int, collection_name: str | None = None ) -> dict | None:
        collection_name = collection_name or self._default_collection_name
        collection = self._get_collection(collection_name)
        return await collection.find_one({"chatId": chat_id})

    async def upsert_contact(
            self, *, user_id: int, chat_id: int, phone: str, full_name: str,usertoken: str, 
            collection_name: str | None = None # <-- Добавляем параметр
        ) -> None:
            collection = self._get_collection(collection_name)
            update_data = {
                "userId": user_id,
                "chatId": chat_id,
                "name": full_name,
                "usertoken": usertoken,
                "date": datetime.now(),
                "eventType": "add_contact",
            }
    
            existing_record = await collection.find_one({"phoneNumber": phone})
    
            if existing_record:
                result = await collection.update_one(
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
            result = await collection.insert_one(insert_data)
            logging.info("Новая запись в MongoDB добавлена с ID: %s", result.inserted_id)

    async def update_usertoken(self, *, phone: str, usertoken: str | None = None) -> None:
        collection = self._get_collection("users")
        update_data = {
            "usertoken": usertoken,
            "date": datetime.now(),
        }        
        existing_record = await collection.find_one({"phoneNumber": phone})        
        if existing_record:
            result = await collection.update_one(
                {"phoneNumber": phone},
                {"$set": update_data},
            )
            logging.info("Usertoken %s обновлен.",phone)
            return
    async def check_request_access(self, phone: str):
        collection = self._get_collection("request_access")
        date = datetime.now()
        start_time = date - timedelta(minutes=10)
        end_time = date    
        filter_query = {
            "phone": phone,
            "date": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
        count = await collection.count_documents(filter_query)    
        if count >= 1:
            return False
        
        insert_data = {
            "phone": phone,  # Исправлено: поле должно называться так же как в фильтре
            "date": datetime.now()  # Добавляем текущую дату
        }
        result = await collection.insert_one(insert_data)
        logging.info("Запись запроса доступов добавлена - ID: %s", result.inserted_id)
        return True

    async def insert_message(self, *, phone: str, message_client:str="", message_ai:str="") -> None:
        collection = self._get_collection("messages")
        insert_data = {
            "phone": phone,
            "message_client": message_client,
            "message_ai": message_ai,
            "date": datetime.now(),
        }
        result = await collection.insert_one(insert_data)
        logging.info("Новая запись в MongoDB добавлена с ID: %s", result.inserted_id)

    async def get_user_messages(self, *, phone: int, limit: int=0, date: Optional[datetime] = None) -> List[dict]:
        collection = self._get_collection("messages")
        filter_query = {"phone": phone}
        if date:
            start_of_day = datetime.combine(date.date(), datetime.min.time())
            end_of_day = datetime.combine(date.date(), datetime.max.time())            
            filter_query["date"] = {
                "$gte": start_of_day,
                "$lte": end_of_day
            }
        cursor = collection.find(filter_query).sort("date", -1)
        messages = await cursor.to_list(length=limit)
        return messages

    async def get_shares(self) -> List[dict]:
        collection = self._get_collection("shares")
        filter_query = {"active": True}
        cursor = collection.find(filter_query)
        shares = await cursor.to_list(length=10)
        return shares
    async def get_faqs(self) -> List[dict]:
        collection = self._get_collection("faqs")
        filter_query = {"active": True}
        cursor = collection.find(filter_query)
        faqs = await cursor.to_list(length=10)
        return faqs

    def close(self):
        if self._client:
            self._client.close()