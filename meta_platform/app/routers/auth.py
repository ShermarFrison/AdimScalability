"""Authentication and user management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas, serializers
from ..database import get_db
from ..security import get_current_user, get_password_hash

router = APIRouter(prefix="/users", tags=["auth"])


@router.post(
    "/register/",
    response_model=schemas.UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Password fields didn't match.")

    existing = db.execute(
        select(models.MetaUser).where(models.MetaUser.email == payload.email.lower())
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    user = models.MetaUser(
        email=payload.email.lower(),
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to register user.")
    db.refresh(user)
    return schemas.UserRegisterResponse(
        message="User registered successfully",
        user=serializers.serialize_user(user, db),
    )


@router.get("/me/", response_model=schemas.UserOut)
def current_user(
    user: models.MetaUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    return serializers.serialize_user(user, db)
