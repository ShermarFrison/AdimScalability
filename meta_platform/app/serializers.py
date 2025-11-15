"""Helper functions to convert ORM models into Pydantic schemas."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas


def serialize_user(user: models.MetaUser, db: Session) -> schemas.UserOut:
    workspace_count = db.execute(
        select(func.count())
        .select_from(models.Workspace)
        .where(
            models.Workspace.owner_id == user.id,
            models.Workspace.status.in_(["provisioning", "active"]),
        )
    ).scalar_one()
    return schemas.UserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        subscription_tier=user.subscription_tier,
        max_workspaces=user.max_workspaces,
        workspace_count=workspace_count,
        can_create_workspace=workspace_count < user.max_workspaces,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


def serialize_workspace(workspace: models.Workspace) -> schemas.WorkspaceOut:
    return schemas.WorkspaceOut(
        id=workspace.id,
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        owner=workspace.owner_id,
        owner_email=workspace.owner.email,
        deployment_type=workspace.deployment_type,
        status=workspace.status,
        instance_url=workspace.instance_url or "",
        tailscale_url=workspace.tailscale_url or "",
        ip_address=workspace.ip_address,
        droplet_id=workspace.droplet_id,
        region=workspace.region,
        vcpu=workspace.vcpu,
        ram_gb=workspace.ram_gb,
        storage_gb=workspace.storage_gb,
        subscription_tier=workspace.subscription_tier,
        monthly_cost=workspace.monthly_cost,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        provisioned_at=workspace.provisioned_at,
        config_data=workspace.config_data or {},
        port_allocation=workspace.get_port_allocation(),
    )


def serialize_otp(otp: models.WorkspaceOTP) -> schemas.OTPOut:
    return schemas.OTPOut(
        id=otp.id,
        workspace=otp.workspace_id,
        workspace_id=otp.workspace.workspace_id,
        workspace_name=otp.workspace.name,
        otp_code=otp.otp_code,
        created_at=otp.created_at,
        expires_at=otp.expires_at,
        used_at=otp.used_at,
        is_active=otp.is_active,
        usage_count=otp.usage_count,
        max_uses=otp.max_uses,
        is_valid=otp.is_valid,
    )


def serialize_log(log: models.ProvisioningLog) -> schemas.ProvisioningLogOut:
    return schemas.ProvisioningLogOut(
        id=log.id,
        workspace=log.workspace_id,
        timestamp=log.timestamp,
        level=log.level,
        message=log.message,
        data=log.data or {},
    )
