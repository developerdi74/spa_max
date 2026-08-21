from maxapi.types import RequestContactButton
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import CallbackButton, LinkButton

from listener.payloads import CallbackAction,CreateVisitPayload,VisitsActionPayload


class Keyboards:
    @staticmethod
    def menu_button1():
        buttons = [[CallbackButton(text="Главное меню", payload=CallbackAction(action="menu").pack())]]
        return ButtonsPayload(buttons=buttons).pack()
    
    @staticmethod
    def menu_button():
        return [CallbackButton(text="Главное меню", payload=CallbackAction(action="menu").pack())]

    @staticmethod
    def main_menu():
        buttons = [
            [CallbackButton(text="Записаться на услугу", payload=CreateVisitPayload(action="create_visit").pack())],
            [CallbackButton(text="История посещений", payload=VisitsActionPayload(action="list_visits").pack())],     
            [CallbackButton(text="Акции", payload=CallbackAction(action="shares").pack())],
            [CallbackButton(text="Вопросы и ответы", payload=CallbackAction(action="faq").pack())],
            [CallbackButton(text="Информация", payload=CallbackAction(action="information_menu").pack())],
            [RequestContactButton(text="Поделиться контактом")],
        ]
        return ButtonsPayload(buttons=buttons).pack()

    @staticmethod
    def information_menu():
        buttons = [
            [LinkButton(text="Наш сайт", url="https://spa-di.ru/")],
            [CallbackButton(text="Информация о центре(адрес и контакты)", payload=CallbackAction(action="information_centers").pack())],
            [LinkButton(text="Связаться с оператором", url="https://max.ru/u/f9LHodD0cOIlpd840ED7t1rf09ShSgek4uLcYf9TOaJHPHCWrFWyGWvhRy8")],
            [CallbackButton(text="Основное меню", payload=CallbackAction(action="menu").pack())],
        ]
        return ButtonsPayload(buttons=buttons).pack()

    @staticmethod
    def request_contact() -> list:
        from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.row(RequestContactButton(text="📱 Поделиться контактом"))
        return [builder.as_markup()]