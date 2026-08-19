import pkgutil
import importlib
from .base_handler import BaseHandler, HandlerRegistry

def discover_handlers():
    """Автоматически импортирует все модули в папке handlers и её подпапках"""
    # __path__ указывает на текущую папку (handlers)
    for _, module_name, _ in pkgutil.walk_packages(__path__, prefix=__name__ + '.'):
        if not module_name.endswith('.base'):
            importlib.import_module(module_name)
    return BaseHandler._registry