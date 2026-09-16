"""[RBAC] issue #200 — Admin: User Management.

The first genuinely NEW admin-only surface this epic adds — reading and
creating rows in the new `User` table (issue #172). No page for this
exists anywhere today; this is the minimal real one, Administrator only.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CreateUserRequest, UpdateUserRequest, UserOut
from app.auth.dependency import require_permission
from app.auth.roles import STAFF_ROLES
from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _actor=Depends(require_permission("manage_users"))) -> list[User]:
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut)
def create_user(
    payload: CreateUserRequest, db: Session = Depends(get_db), _actor=Depends(require_permission("manage_users"))
) -> User:
    if payload.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'.")
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(status_code=400, detail=f"A user with email '{payload.email}' already exists.")

    user = User(name=payload.name, email=payload.email, role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("manage_users")),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if payload.role is not None:
        if payload.role not in STAFF_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'.")
        user.role = payload.role
    if payload.name is not None:
        user.name = payload.name

    db.commit()
    db.refresh(user)
    return user
