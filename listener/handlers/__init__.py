import pkgutil
import importlib
import logging
from .base_handler import BaseHandler, HandlerRegistry

logger = logging.getLogger(__name__)

def discover_handlers():
    """Автоматически импортирует все модули в папке handlers и её подпапках"""
    # Очищаем реестр перед новым обнаружением (важно для Gunicorn reload)
    BaseHandler._registry.clear()
    logger.info("Начало обнаружения хендлеров...")
    
    # __path__ указывает на текущую папку (handlers)
    for importer, module_name, is_pkg in pkgutil.walk_packages(__path__, prefix=__name__ + '.'):
        if module_name.endswith('.base') or module_name.endswith('__init__'):
            continue
        
        logger.info("Импорт модуля: %s", module_name)
        try:
            module = importlib.import_module(module_name)
            # Проверяем, есть ли в модуле классы-наследники BaseHandler
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseHandler) and attr != BaseHandler:
                    logger.info("Найден хендлер в модуле %s: %s", module_name, attr_name)
        except Exception as e:
            logger.error("Ошибка импорта модуля %s: %s", module_name, e)
    
    logger.info("Всего найдено хендлеров: %d", len(BaseHandler._registry))
    for cls in BaseHandler._registry:
        logger.info("  - %s", cls.__name__)
    
    return BaseHandler._registry