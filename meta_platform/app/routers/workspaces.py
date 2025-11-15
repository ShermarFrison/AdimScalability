"""Workspace management endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas, serializers
from ..database import get_db
from ..security import get_current_user

router = APIRouter(tags=["workspaces"])


def _get_workspace(
    workspace_id: int, user: models.MetaUser, db: Session
) -> models.Workspace:
    workspace = db.execute(
        select(models.Workspace)
        .where(
            models.Workspace.id == workspace_id,
            models.Workspace.owner_id == user.id,
        )
        .options(selectinload(models.Workspace.owner))
    ).scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return workspace


def _active_workspace_count(user_id: int, db: Session) -> int:
    return db.execute(
        select(func.count())
        .select_from(models.Workspace)
        .where(
            models.Workspace.owner_id == user_id,
            models.Workspace.status.in_(["provisioning", "active"]),
        )
    ).scalar_one()


@router.get("/workspaces/", response_model=list[schemas.WorkspaceOut])
def list_workspaces(
    user: models.MetaUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    workspaces = db.execute(
        select(models.Workspace)
        .where(models.Workspace.owner_id == user.id)
        .order_by(models.Workspace.created_at.desc())
        .options(selectinload(models.Workspace.owner))
    ).scalars()
    return [serializers.serialize_workspace(ws) for ws in workspaces]


@router.post(
    "/workspaces/",
    response_model=schemas.WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    payload: schemas.WorkspaceCreate,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if _active_workspace_count(user.id, db) >= user.max_workspaces:
        raise HTTPException(
            status_code=400,
            detail="You have reached the maximum number of workspaces for your subscription tier.",
        )

    data = payload.model_dump()
    workspace = models.Workspace(
        owner_id=user.id,
        name=data["name"],
        deployment_type=data["deployment_type"],
        region=data.get("region") or "",
        vcpu=data.get("vcpu") or 2,
        ram_gb=data.get("ram_gb") or 4,
        storage_gb=data.get("storage_gb") or 50,
    )
    db.add(workspace)
    db.flush()

    otp = models.WorkspaceOTP(workspace=workspace, max_uses=0)
    log = models.ProvisioningLog(
        workspace=workspace,
        level="info",
        message=f"Workspace {workspace.workspace_id} created by {user.email}",
        data={"otp": otp.otp_code},
    )
    db.add_all([otp, log])
    db.commit()
    db.refresh(workspace)
    return serializers.serialize_workspace(workspace)


@router.get("/workspaces/{workspace_id}/", response_model=schemas.WorkspaceOut)
def workspace_detail(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    return serializers.serialize_workspace(workspace)


@router.patch("/workspaces/{workspace_id}/", response_model=schemas.WorkspaceOut)
def update_workspace(
    workspace_id: int,
    payload: schemas.WorkspaceUpdate,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    updates: dict[str, Any] = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is None:
            continue
        setattr(workspace, field, value)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return serializers.serialize_workspace(workspace)


@router.delete("/workspaces/{workspace_id}/", response_model=schemas.Message)
def delete_workspace(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    workspace.mark_decommissioned()
    log = models.ProvisioningLog(
        workspace=workspace,
        level="info",
        message=f"Workspace {workspace.workspace_id} decommissioned",
    )
    db.add_all([workspace, log])
    db.commit()
    return schemas.Message(message="Workspace decommissioned.")


@router.post(
    "/workspaces/{workspace_id}/mark-active/",
    response_model=schemas.WorkspaceOut,
)
def mark_workspace_active(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    workspace.mark_provisioned()
    log = models.ProvisioningLog(
        workspace=workspace,
        level="info",
        message="Workspace marked as active",
    )
    db.add_all([workspace, log])
    db.commit()
    db.refresh(workspace)
    return serializers.serialize_workspace(workspace)


@router.post(
    "/workspaces/{workspace_id}/generate-otp/",
    response_model=schemas.OTPOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_workspace_otp(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    otp = models.WorkspaceOTP(workspace=workspace, max_uses=0)
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return serializers.serialize_otp(otp)


@router.get(
    "/workspaces/{workspace_id}/otps/",
    response_model=list[schemas.OTPOut],
)
def list_workspace_otps(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    otps = db.execute(
        select(models.WorkspaceOTP)
        .where(models.WorkspaceOTP.workspace_id == workspace.id)
        .order_by(models.WorkspaceOTP.created_at.desc())
        .options(selectinload(models.WorkspaceOTP.workspace))
    ).scalars()
    return [serializers.serialize_otp(otp) for otp in otps]


@router.get(
    "/workspaces/{workspace_id}/logs/",
    response_model=list[schemas.ProvisioningLogOut],
)
def workspace_logs(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(workspace_id, user, db)
    logs = db.execute(
        select(models.ProvisioningLog)
        .where(models.ProvisioningLog.workspace_id == workspace.id)
        .order_by(models.ProvisioningLog.timestamp.desc())
        .limit(50)
    ).scalars()
    return [serializers.serialize_log(log) for log in logs]
