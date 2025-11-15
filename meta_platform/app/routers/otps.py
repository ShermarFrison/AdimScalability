"""OTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas, serializers
from ..database import get_db
from ..security import get_current_user

router = APIRouter(tags=["otps"])


@router.get("/otps/", response_model=list[schemas.OTPOut])
def list_otps(
    user: models.MetaUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    otps = db.execute(
        select(models.WorkspaceOTP)
        .join(models.Workspace)
        .where(models.Workspace.owner_id == user.id)
        .order_by(models.WorkspaceOTP.created_at.desc())
        .options(selectinload(models.WorkspaceOTP.workspace))
    ).scalars()
    return [serializers.serialize_otp(otp) for otp in otps]


@router.post(
    "/otps/validate/",
    response_model=schemas.OTPValidationResponse,
)
def validate_otp(
    payload: schemas.OTPValidationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    otp_code = payload.otp.upper()
    otp = db.execute(
        select(models.WorkspaceOTP)
        .where(models.WorkspaceOTP.otp_code == otp_code)
        .options(selectinload(models.WorkspaceOTP.workspace))
    ).scalar_one_or_none()
    if not otp or not otp.is_valid:
        raise HTTPException(status_code=400, detail="OTP is invalid or has expired.")

    client_ip = request.client.host if request.client else None
    otp.mark_used(client_ip)
    log = models.ProvisioningLog(
        workspace=otp.workspace,
        level="info",
        message=f"OTP validated from IP {client_ip or 'unknown'}",
        data={"otp": otp.otp_code},
    )
    db.add_all([otp, log])
    db.commit()
    details = otp.get_connection_details()
    return schemas.OTPValidationResponse(**details)
