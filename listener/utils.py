def get_chat_id(event) -> int | None:
    chat_id = getattr(event, "chat_id", None)
    if chat_id:
        return chat_id

    message = getattr(event, "message", None)
    if message and hasattr(message, "recipient") and message.recipient:
        return message.recipient.chat_id

    return None
