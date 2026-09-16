"""[RBAC] issue #204 — Admin: System Configuration.

A real, DB-backed key-value settings surface, Administrator only — see
`SystemSetting`'s own docstring (app/db/models.py) for why this exists
instead of a fabricated wrapper around the env-var-driven app/config.py.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import SystemSettingOut, UpdateSystemSettingRequest
from app.auth.dependency import require_permission
from app.db.database import get_db
from app.db.models import SystemSetting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SystemSettingOut])
def list_settings(
    db: Session = Depends(get_db), _actor=Depends(require_permission("manage_system_settings"))
) -> list[SystemSetting]:
    return db.query(SystemSetting).order_by(SystemSetting.key).all()


@router.patch("/{key}", response_model=SystemSettingOut)
def update_setting(
    key: str,
    payload: UpdateSystemSettingRequest,
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("manage_system_settings")),
) -> SystemSetting:
    setting = db.get(SystemSetting, key)
    if setting is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    setting.value = payload.value
    db.commit()
    db.refresh(setting)
    return setting
