"""[Omnichannel] issue #135 — Channel status management.

The first real read/write API surface over the `Channel` table (issue
#132) — list all 5 seeded channels with their current status, and toggle
a channel active/inactive. Deliberately narrow: this is a Settings-level
control, not a full CRUD API — nothing here creates or deletes a
`Channel` row (the 5 rows are seeded once, in app/db/seed.py, and that's
the only place new ones are meant to appear until a later issue actually
needs that).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ChannelOut, UpdateChannelStatusRequest
from app.db.database import get_db
from app.db.models import Channel

router = APIRouter(prefix="/api/channels", tags=["channels"])

_VALID_STATUSES = {"active", "inactive", "not_configured"}


def _to_channel_out(channel: Channel) -> ChannelOut:
    return ChannelOut(
        id=channel.id,
        key=channel.key,
        display_name=channel.display_name,
        status=channel.status,
        config=channel.config,
    )


@router.get("", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db)) -> list[ChannelOut]:
    channels = db.query(Channel).order_by(Channel.id).all()
    return [_to_channel_out(c) for c in channels]


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel_status(channel_id: int, payload: UpdateChannelStatusRequest, db: Session = Depends(get_db)) -> ChannelOut:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    if payload.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{payload.status}'.")

    # Never let a channel claim to be "active" while it's still honestly
    # "not_configured" — see Channel's own docstring: real transport for
    # WhatsApp/Instagram/Messenger doesn't exist yet in this environment,
    # and activating one here would silently promise working delivery
    # that a later channel-adapter call would only fail to provide. A
    # channel can only move to "active" from "inactive" (i.e. it must
    # already have been configured at least once); "not_configured" can
    # only be left via a real setup step this issue doesn't add.
    if payload.status == "active" and channel.status == "not_configured":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate '{channel.key}' — it has not been configured yet.",
        )

    channel.status = payload.status
    db.commit()
    db.refresh(channel)
    return _to_channel_out(channel)
