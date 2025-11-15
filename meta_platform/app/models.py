"""SQLAlchemy models for the FastAPI meta platform."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    JSON,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


def generate_workspace_id() -> str:
    """Generate unique workspace ID similar to the Django version."""
    return "ws" + secrets.token_hex(3)[:5]


def generate_otp() -> str:
    """Generate a cryptographically secure OTP."""
    return secrets.token_hex(3).upper()


def otp_expiration() -> datetime:
    """Default OTP expiration timestamp (24 hours)."""
    return datetime.now(timezone.utc) + timedelta(hours=24)


class MetaUser(Base):
    """Meta platform user who owns provisioned workspaces."""

    __tablename__ = "meta_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(150), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    subscription_tier = Column(String(20), default="free", nullable=False)
    max_workspaces = Column(Integer, default=1, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")

    @property
    def workspace_count(self) -> int:
        active_statuses = {"provisioning", "active"}
        return len([ws for ws in self.workspaces if ws.status in active_statuses])

    @property
    def can_create_workspace(self) -> bool:
        return self.workspace_count < self.max_workspaces


class Workspace(Base):
    """Provisioned workspace metadata."""

    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(String(20), unique=True, nullable=False, default=generate_workspace_id)
    name = Column(String(100), nullable=False)
    owner_id = Column(Integer, ForeignKey("meta_users.id"), nullable=False)

    deployment_type = Column(String(20), nullable=False)
    status = Column(String(20), default="provisioning", nullable=False)

    instance_url = Column(String(255), default="", nullable=False)
    tailscale_url = Column(String(255), default="", nullable=False)
    ip_address = Column(String(45))

    droplet_id = Column(String(100), default="", nullable=False)
    region = Column(String(50), default="", nullable=False)

    vcpu = Column(Integer, default=2, nullable=False)
    ram_gb = Column(Integer, default=4, nullable=False)
    storage_gb = Column(Integer, default=50, nullable=False)

    subscription_tier = Column(String(20), default="starter", nullable=False)
    monthly_cost = Column(Numeric(10, 2), default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    provisioned_at = Column(DateTime(timezone=True))
    decommissioned_at = Column(DateTime(timezone=True))

    config_data = Column(MutableDict.as_mutable(JSON), default=dict, nullable=False)

    owner = relationship("MetaUser", back_populates="workspaces")
    otps = relationship("WorkspaceOTP", back_populates="workspace", cascade="all, delete-orphan")
    logs = relationship("ProvisioningLog", back_populates="workspace", cascade="all, delete-orphan")

    def mark_provisioned(self) -> None:
        self.status = "active"
        self.provisioned_at = datetime.now(timezone.utc)

    def mark_failed(self) -> None:
        self.status = "failed"

    def mark_decommissioned(self) -> None:
        self.status = "decommissioned"
        self.decommissioned_at = datetime.now(timezone.utc)

    def get_port_allocation(self) -> Dict[str, int]:
        """Replicates the deterministic port allocation from the Django model."""
        hash_value = int(hashlib.md5(self.workspace_id.encode()).hexdigest()[:6], 16)
        base_offset = (hash_value % 1000) * 10
        return {
            "daphne": 8000 + base_offset,
            "redis": 6379 + base_offset,
            "qdrant_http": 6333 + base_offset,
            "qdrant_grpc": 6334 + base_offset,
            "neo4j": 7687 + base_offset,
        }

    def get_connection_details(self) -> Dict[str, str | None]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "endpoints": {
                "cloud": self.instance_url or None,
                "tailscale": self.tailscale_url or None,
                "ip": self.ip_address or None,
            },
            "status": self.status,
            "subscription": self.subscription_tier,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "features": (self.config_data or {}).get("features", {}),
        }


class WorkspaceOTP(Base):
    """One-time passwords that client apps use to discover workspaces."""

    __tablename__ = "workspace_otps"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    otp_code = Column(String(12), unique=True, nullable=False, default=generate_otp, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), default=otp_expiration, nullable=False)
    used_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)

    usage_count = Column(Integer, default=0, nullable=False)
    max_uses = Column(Integer, default=1, nullable=False)
    last_used_ip = Column(String(45))

    workspace = relationship("Workspace", back_populates="otps")

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        if self.max_uses > 0 and self.usage_count >= self.max_uses:
            return False
        if self.workspace.status not in {"active", "provisioning"}:
            return False
        return True

    def mark_used(self, ip_address: str | None = None) -> None:
        self.usage_count += 1
        self.used_at = datetime.now(timezone.utc)
        if ip_address:
            self.last_used_ip = ip_address
        if self.max_uses > 0 and self.usage_count >= self.max_uses:
            self.is_active = False

    def get_connection_details(self) -> Dict[str, str | Dict[str, str | None]]:
        details = self.workspace.get_connection_details()
        details["otp"] = self.otp_code
        return details


class ProvisioningLog(Base):
    """Audit log for provisioning steps."""

    __tablename__ = "provisioning_logs"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    level = Column(String(10), default="info", nullable=False)
    message = Column(String, nullable=False)
    data = Column(MutableDict.as_mutable(JSON), default=dict, nullable=False)

    workspace = relationship("Workspace", back_populates="logs")
