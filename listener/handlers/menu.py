from maxapi import Dispatcher, F
from maxapi.types import MessageCallback

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.payloads import CallbackAction
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format


class MenuHandler(BaseHandler):
    def register(self, dp: Dispatcher) -> None:
        dp.message_callback(CallbackAction.filter(F.action == "menu"))(self.handle)
        dp.message_callback(CallbackAction.filter(F.action == "information_menu"))(self.handle)

    async def handle(self, event: MessageCallback, payload: CallbackAction) -> None:
        text = as_html(
            Heading("🌸 Добро пожаловать в «Другое измерение»!") +
            "\n\n" +
            "Мы рады видеть вас в нашем центре красоты и здоровья." +
            "\n\n" +
            "✨ Выберите действие:"
        )
        text_about = as_html(
            Heading("📋 Полезная информация") +
            "\n\n" +
            "🌐 " + Bold("Сайт:") +
            "\n" + "https://spa-di.ru" +
            "\n\n" +
            "📞 " + Bold("Контакты:") +
            "\n" + "+7 (3519) 580-111" +
            "\n" + "Ежедневно: 9:00 – 21:00" +
            "\n\n" +
            "💬 " + Bold("Мессенджеры:") +
            "\n" + "WhatsApp: +7 (3519) 580-111" +
            "\n" + "Telegram: @drugoe_izmerenie" +
            "\n\n" +
            "📍 " + Bold("Адрес:") +
            "\n" + "ул. Ленина, 27, Магнитогорск" +
            "\n\n" +
            "✨ " + Bold("О центре:") +
            "\n" + "«Другое измерение» — центр красоты и здоровья с 20-летней историей. " +
            "Мы объединили лучшие мировые технологии и проверенные методики. " +
            "95% клиентов остаются с нами после первого визита."
        )
        if(payload.action == "menu"):
            await event.answer(
                new_text=text,
                attachments=[Keyboards.main_menu()],
                format=Format.HTML,
            )

        if(payload.action == "information_menu"):
            await event.answer(
                new_text=text_about,
                attachments=[Keyboards.information_menu()],
                format=Format.HTML,
            )
