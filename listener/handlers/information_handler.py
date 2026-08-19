from maxapi import Dispatcher, F
from maxapi.types import MessageCallback

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.payloads import CallbackAction
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format


class InformationCenterHandler(BaseHandler):
    def register(self, dp: Dispatcher) -> None:
        dp.message_callback(CallbackAction.filter(F.action == "information_centers"))(self.handle)

    async def handle(self, event: MessageCallback, payload: CallbackAction) -> None:
        text = as_html(
            Heading("🌸 О центре «Другое измерение»") +
            "\n\n" +
            "Мы — центр красоты и здоровья, где ваши желания становятся реальностью." +
            "\n\n" +
            "✨ " + Bold("20 лет доверия") +
            "\nНа рынке с 2006 года. Каждый второй в городе слышал о нас." +
            "\n\n" +
            "💆 " + Bold("Комплексный подход") +
            "\nДиагностика лица, тела и волос — передовые технологии для точного результата." +
            "\n\n" +
            "🏆 " + Bold("Экспертность") +
            "\nСпециалисты с фундаментальным знанием анатомии, регулярное обучение." +
            "\n\n" +
            "📋 " + Bold("Медицинская лицензия") +
            "\nВся деятельность сертифицирована и разрешена на территории РФ." +
            "\n\n" +
            "📍 ул. Ленина, 27" +
            "\n📞 +7 (3519) 580-111"
        )
        await event.answer(
            new_text=text,
            format=Format.HTML,
            attachments=[Keyboards.main_menu()],
        )