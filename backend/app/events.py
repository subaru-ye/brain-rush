from __future__ import annotations

from sqlalchemy.orm import Session

from .models import ProductEvent, now_utc
from .schemas import ProductEventRequest, ProductEventResponse


def save_product_event(
    db: Session,
    user_id: str | None,
    payload: ProductEventRequest,
) -> ProductEventResponse:
    event = ProductEvent(
        user_id=user_id,
        client_id=payload.clientId,
        event_name=payload.eventName,
        page=payload.page,
        session_id=payload.sessionId,
        topic=payload.topic,
        properties_json=payload.properties,
        occurred_at=payload.occurredAt or now_utc(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return ProductEventResponse(id=event.id, createdAt=event.created_at)
