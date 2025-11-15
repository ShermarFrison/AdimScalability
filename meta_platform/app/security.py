"""Security helpers for the FastAPI meta platform."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
basic_scheme = HTTPBasic()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(basic_scheme),
    db: Session = Depends(get_db),
) -> models.MetaUser:
    user = db.execute(
        select(models.MetaUser).where(models.MetaUser.email == credentials.username.lower())
    ).scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user
