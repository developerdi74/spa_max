from maxapi import Dispatcher, F
from maxapi.types import MessageCallback

from listener.handlers.base_handler import BaseHandler
from listener.keyboards import Keyboards
from listener.payloads import CallbackAction
from maxapi.utils.formatting import Bold, Heading, Link, as_html
from maxapi.enums.format import Format
from storage import MongoStorage
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
        dp.message_callback(CallbackAction.filter(F.action == "shares"))(self.handle)

    async def handle(self, event: MessageCallback, payload: CallbackAction) -> None:
        shares = await self._storage.get_shares()
        buttons=[]
        if not shares:
            await event.answer(
                new_text=as_html("Действующих акций пока нет, но скоро будет!"),
                format=Format.HTML,
                attachments=[Keyboards.main_menu()],
            )
            return
        
        for share in shares:
            buttons=[]
            text = as_html(Heading("АКЦИЯ: "+share["name"])+f"\n\n"+share["text"])
            if share.get("service_id"):
                service_id = share.get("service_id")
                service_name = share.get("service_name","Записаться")
                buttons.append([
                    CallbackButton(
                        text=service_name,
                        payload=CreateVisitPayload(
                            step="get_staff_and_date",
                            category_id="",
                            services_id=str(service_id),
                            services_title=service_name
                        ).pack()
                    )
                ])          

            buttons.append([CallbackButton(text="Основное меню", payload=CallbackAction(action="menu").pack())]);
            payload_buttons = ButtonsPayload(buttons=buttons).pack()
            await event.send(
                text=text,
                format=Format.HTML,
                attachments=[payload_buttons],
                #attachments=[Keyboards.main_menu()],
            )