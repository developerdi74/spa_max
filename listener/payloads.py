from maxapi.filters.callback_payload import CallbackPayload

class CreateVisitPayload(CallbackPayload, prefix="create_visit"):
    category_id: str = ""
    services_id: str = ""
    step: str = ""
    staff_id: str = ""
    staff_name: str = ""
    select_date: str = ""
    datetime: str = ""
    services_title:str = ""
    action: str = "create_visit"

class CallbackAction(CallbackPayload, prefix="visits"):
    action: str

class VisitsActionPayload(CallbackPayload, prefix="visits"):
    action_filter: str = "list_visits"
    action: str = ""
    visit_id: str = ""