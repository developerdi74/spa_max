import os
from dataclasses import dataclass

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


@dataclass(frozen=True)
class Config:
    mongo_uri: str
    db_name: str
    collection_name: str
    salon_id: str
    salon_key: str
    webhook_url: str
    webhook_secret: str | None
    webhook_host: str
    webhook_port: int
    webhook_path: str
    ai_activated: str
    ai_key: str
    ai_project: str
    ai_url: str
    ai_model: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            mongo_uri=os.getenv("MONGO_URI", ""),
            db_name=os.getenv("DB_NAME", ""),
            collection_name=os.getenv("COLLECTION_NAME", ""),
            salon_id=os.getenv("SALON_ID", ""),
            salon_key=os.getenv("API_KEY", ""),
            webhook_url=os.getenv("WEBHOOK_URL_SUBSCRIBE", ""),
            webhook_secret=os.getenv("WEBHOOK_SECRET") or None,
            webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
            webhook_port=int(os.getenv("WEBHOOK_PORT_HTTPS", "8880")),
            webhook_path=os.getenv("WEBHOOK_PATH", "/webhook"),
            ai_activated=os.getenv("AI_ACTIVATED", "0"),
            ai_key=os.getenv("AI_SECRET",""),
            ai_url=os.getenv("AI_URL",""),
            ai_project=os.getenv("AI_PROJECT",""),
            ai_model=os.getenv("AI_MODEL","")
        )
