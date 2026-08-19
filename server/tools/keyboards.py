from maxapi.types import RequestContactButton
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import CallbackButton, LinkButton

from .payloads import CallbackAction

class Keyboards:
    @staticmethod
    def menu_button():
        buttons = [[CallbackButton(text="Главное меню", payload=CallbackAction(action="menu").pack())]]
        return ButtonsPayload(buttons=buttons).pack()

    """@staticmethod
    def main_menu():
        buttons = [
            [CallbackButton(text="Записаться на услугу", payload=CreateVisitPayload(action="create_visit").pack())],
            [CallbackButton(text="История посещений", payload=VisitsActionPayload(action="list_visits").pack())],     
            [CallbackButton(text="Информация", payload=CallbackAction(action="information_menu").pack())],
            [RequestContactButton(text="Поделиться контактом")],
        ]
        return ButtonsPayload(buttons=buttons).pack()"""