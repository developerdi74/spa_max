from maxapi import Dispatcher, F
from maxapi.types import MessageCallback

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.payloads import CallbackAction
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format
from listener.storage import MongoStorage
from listener.services import AIHelperService
from listener.services.salon1c_service import Salon1CService
from maxapi.types.attachments.attachment import ButtonsPayload
from listener.payloads import CreateVisitPayload, CallbackAction
from maxapi.types.attachments.buttons import CallbackButton



class InformationCenterHandler(BaseHandler):
    def __init__(self, storage: MongoStorage, aiservice: AIHelperService, salon1c_service: Salon1CService):
        self._storage = storage
        self._service = aiservice
        self._salon_service = salon1c_service
    def register(self, dp: Dispatcher) -> None:
        dp.message_callback(CallbackAction.filter(F.action == "faq"))(self.handle)

    async def handle(self, event: MessageCallback, payload: CallbackAction) -> None:
        faqs = await self._storage.get_faqs()
        buttons=[]
        if not faqs:
            await event.answer(
                new_text=as_html("Извинте, пока раздел пуст!"),
                format=Format.HTML,
                attachments=[Keyboards.main_menu()],
            )
            return
        text = ""
        counter = 0
        for faq in faqs:
            if(counter == 3):
                await event.send(
                    text=text,
                    format=Format.HTML,
                )
                counter+= 0
                text=""
                
            text += as_html(Bold(faq["question"])+"\n"+faq["answer"]+"\n\n")
            counter += 1

        buttons.append(Keyboards.menu_button());
        payload_buttons = ButtonsPayload(buttons=buttons).pack()
        await event.send(
            text=text,
            format=Format.HTML,
            attachments=[payload_buttons],
        )