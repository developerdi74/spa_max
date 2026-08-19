"""
Сервисы для бизнес-логики.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import html as html_lib
import asyncio

from maxapi import Bot
from maxapi.utils.formatting import Bold, Heading, as_html
from maxapi.enums.format import Format

from ..models.newsletter import NewsletterDocument, NewsletterStatus
from ..repositories.database import (
    DatabaseManager,
    NewsletterRepository,
    NewsletterLogRepository,
    UserRepository,
)
from ..config.settings import settings
from ..tools.keyboards import Keyboards

logger = logging.getLogger(__name__)


class NewsletterService:
    """Сервис для управления рассылками."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        bot: Bot,
    ):
        self.db_manager = db_manager
        self.bot = bot
        
        # Репозитории
        self.newsletter_repo: NewsletterRepository = db_manager.newsletters
        self.newsletter_log_repo: NewsletterLogRepository = db_manager.newsletter_logs
        self.user_repo: UserRepository = db_manager.users
    
    @staticmethod
    def render_newsletter_text(text: str) -> str:
        """
        Экранируем HTML и переводим переносы строк в <br>.
        Если потом захочешь полноценные HTML-шаблоны, можно сделать отдельный Jinja-шаблон письма.
        """
        return html_lib.escape(text or "").replace("\n", "<br>")
    
    async def send_newsletter(self, newsletter_id: str, attempt: int) -> None:
        """
        Фоновая отправка рассылки.
        attempt нужен, чтобы одну и ту же рассылку можно было запускать повторно,
        но в рамках одной попытки не слать дубли.
        """
        try:
            # Фиксируем, что рассылка началась, и защищаемся от параллельного запуска
            if not await self.newsletter_repo.mark_as_running(newsletter_id, attempt):
                logger.info(f"⏭️ Рассылка {newsletter_id} уже запускается или не найдена")
                return
            
            newsletter = await self.newsletter_repo.get_by_id(newsletter_id)
            if not newsletter:
                logger.warning(f"⚠️ Рассылка {newsletter_id} не найдена")
                return
            
            message_text = newsletter.text
            message_name = self.render_newsletter_text(newsletter.name)
            
            sent = 0
            errors = 0
            processed = 0
            
            async for user in self.user_repo.get_users_with_chat_ids():
                chat_id = user.get("chatId")
                user_name = user.get("name", "")
                if not chat_id:
                    continue
                
                try:
                    # Проверяем, не было ли уже отправлено сообщение
                    if await self.newsletter_log_repo.already_sent(
                        newsletter_id, attempt, chat_id
                    ):
                        continue
                    
                    # Обработка текста с разделением по #
                    if "#" in message_text:
                        result = message_text.split("#")
                        message_text = ""
                        for str_item in result:
                            message_text += str_item + "\n"
                    
                    # Формирование текста сообщения
                    text = as_html(Heading(message_name) + "\n\n")
                    text += message_text
                    if "{name}" in text:
                        text = text.replace("{name}", user_name)
                    
                    # Получение кнопок
                    attachments = Keyboards.menu_button()
                    
                    # Отправка сообщения
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        format=Format.HTML,
                        attachments=[attachments]
                    )
                    
                    # Логирование успешной отправки
                    await self.newsletter_log_repo.log_send(
                        newsletter_id=newsletter_id,
                        attempt=attempt,
                        chat_id=chat_id,
                        sent=True,
                        error=None,
                    )
                    
                    sent += 1
                    
                except Exception as e:
                    errors += 1
                    logger.error(f"❌ Ошибка отправки сообщения пользователю {chat_id}: {e}")
                    
                    try:
                        # Логирование ошибки
                        await self.newsletter_log_repo.log_send(
                            newsletter_id=newsletter_id,
                            attempt=attempt,
                            chat_id=chat_id,
                            sent=False,
                            error=str(e),
                        )
                    except Exception as log_error:
                        logger.error(f"❌ Не удалось сохранить ошибку рассылки: {log_error}")
                
                processed += 1
                
                # Обновление прогресса каждые N сообщений
                if processed % settings.NEWSLETTER_BATCH_SIZE == 0:
                    await self.newsletter_repo.update_progress(
                        newsletter_id, sent, errors
                    )
                
                # Защита от rate limit
                await asyncio.sleep(settings.NEWSLETTER_RATE_LIMIT_DELAY)
            
            # Завершение рассылки
            await self.newsletter_repo.complete(newsletter_id, sent, errors)
            
        except Exception as e:
            logger.error(f"❌ Ошибка рассылки {newsletter_id}: {e}", exc_info=True)
            
            try:
                await self.newsletter_repo.fail(newsletter_id, str(e))
            except Exception:
                pass
    
    async def validate_newsletter_status_for_edit(
        self,
        newsletter: Optional[NewsletterDocument]
    ) -> bool:
        """Проверка, можно ли редактировать рассылку."""
        if not newsletter:
            return False
        
        if newsletter.status in [NewsletterStatus.queued, NewsletterStatus.running]:
            return False
        
        return True
    
    async def validate_newsletter_status_for_delete(
        self,
        newsletter: Optional[NewsletterDocument]
    ) -> bool:
        """Проверка, можно ли удалить рассылку."""
        if not newsletter:
            return False
        
        if newsletter.status in [NewsletterStatus.queued, NewsletterStatus.running]:
            return False
        
        return True
    
    async def validate_newsletter_status_for_send(
        self,
        newsletter: Optional[NewsletterDocument]
    ) -> bool:
        """Проверка, можно ли запустить рассылку."""
        if not newsletter:
            return False
        
        if newsletter.status in [NewsletterStatus.queued, NewsletterStatus.running]:
            return False
        
        return True
