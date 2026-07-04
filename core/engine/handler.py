from core.contracts import IncomingEvent, OutgoingMessage
from core.engine.llm import generate_text


async def handle_event(event: IncomingEvent) -> OutgoingMessage:
    response_text = await generate_text(
        session_id=event.external_session_id,
        user_message=event.text,
    )

    return OutgoingMessage(
        external_session_id=event.external_session_id,
        platform=event.platform,
        text=response_text,
    )
