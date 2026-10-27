from pydantic import AwareDatetime, BaseModel

from app.models.enums import NotificationKind


class NotificationOut(BaseModel):
    id: int
    kind: NotificationKind
    title: str
    body: str
    entity_type: str | None
    entity_id: int | None
    created_at: AwareDatetime
    read_at: AwareDatetime | None


class NotificationListOut(BaseModel):
    unread: int
    items: list[NotificationOut]
