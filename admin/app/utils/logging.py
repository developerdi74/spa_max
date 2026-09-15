"""
Утилиты для логирования.
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_dir: Path,
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5
) -> None:
    """
    Настройка логирования.
    
    Args:
        log_dir: Директория для логов.
        log_level: Уровень логирования.
        max_bytes: Максимальный размер одного файла лога.
        backup_count: Количество файлов резервных копий.
    """
    log_dir.mkdir(exist_ok=True)
    
    # Файловый хендлер для логов запросов (ротация)
    request_file_handler = RotatingFileHandler(
        log_dir / "webhook_requests.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    request_file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    )
    
    request_logger = logging.getLogger('webhook_requests')
    request_logger.setLevel(logging.INFO)
    request_logger.addHandler(request_file_handler)
    request_logger.propagate = False  # Не дублировать в общий лог
    
    # Общий логгер
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_request_logger() -> logging.Logger:
    """Получение логгера для запросов."""
    return logging.getLogger('webhook_requests')
