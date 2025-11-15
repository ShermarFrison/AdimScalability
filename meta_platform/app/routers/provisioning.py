"""Provisioning management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user
from ..provisioning.orchestrator import WorkspaceOrchestrator, ProvisioningError

router = APIRouter(tags=["provisioning"])


@router.post(
    "/workspaces/{workspace_id}/provision/",
    response_model=schemas.Message,
)
def manually_provision_workspace(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger workspace provisioning.

    Useful for retry if automatic provisioning failed.
    """
    workspace = db.execute(
        select(models.Workspace)
        .where(
            models.Workspace.id == workspace_id,
            models.Workspace.owner_id == user.id,
        )
    ).scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if workspace.status == "active":
        raise HTTPException(
            status_code=400,
            detail="Workspace is already provisioned and active."
        )

    orchestrator = WorkspaceOrchestrator(db)
    try:
        result = orchestrator.provision_workspace(workspace)
        return schemas.Message(
            message=f"Workspace provisioned successfully at {result.get('instance_url')}"
        )
    except ProvisioningError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Provisioning failed: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/decommission/",
    response_model=schemas.Message,
)
def decommission_workspace(
    workspace_id: int,
    user: models.MetaUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Decommission workspace and stop all services.

    This will:
    - Stop Docker containers
    - Remove volumes
    - Mark workspace as decommissioned
    """
    workspace = db.execute(
        select(models.Workspace)
        .where(
            models.Workspace.id == workspace_id,
            models.Workspace.owner_id == user.id,
        )
    ).scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if workspace.status == "decommissioned":
        raise HTTPException(
            status_code=400,
            detail="Workspace is already decommissioned."
        )

    orchestrator = WorkspaceOrchestrator(db)
    try:
        orchestrator.stop_workspace(workspace)
        return schemas.Message(message="Workspace decommissioned successfully.")
    except ProvisioningError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Decommissioning failed: {str(e)}"
        )
