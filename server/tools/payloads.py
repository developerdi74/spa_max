from maxapi.filters.callback_payload import CallbackPayload

class CallbackAction(CallbackPayload, prefix="visits"):
    action: str