"""Pydantic schemas for API I/O."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Message(BaseModel):
    message: str


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    subscription_tier: str
    max_workspaces: int
    workspace_count: int
    can_create_workspace: bool
    email_verified: bool
    created_at: datetime


class UserRegisterResponse(BaseModel):
    message: str
    user: UserOut


class WorkspaceBase(BaseModel):
    name: str
    deployment_type: str
    region: Optional[str] = ""
    vcpu: Optional[int] = 2
    ram_gb: Optional[int] = 4
    storage_gb: Optional[int] = 50


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    deployment_type: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    instance_url: Optional[str] = None
    tailscale_url: Optional[str] = None
    ip_address: Optional[str] = None
    subscription_tier: Optional[str] = None
    config_data: Optional[Dict[str, Any]] = None


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: str
    name: str
    owner: int
    owner_email: EmailStr
    deployment_type: str
    status: str
    instance_url: Optional[str]
    tailscale_url: Optional[str]
    ip_address: Optional[str]
    droplet_id: Optional[str]
    region: Optional[str]
    vcpu: int
    ram_gb: int
    storage_gb: int
    subscription_tier: str
    monthly_cost: Decimal
    created_at: datetime
    updated_at: datetime
    provisioned_at: Optional[datetime]
    config_data: Dict[str, Any]
    port_allocation: Dict[str, int]


class OTPOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace: int
    workspace_id: str
    workspace_name: str
    otp_code: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    is_active: bool
    usage_count: int
    max_uses: int
    is_valid: bool


class OTPValidationRequest(BaseModel):
    otp: str = Field(max_length=12)


class OTPValidationResponse(BaseModel):
    workspace_id: str
    name: str
    otp: str
    endpoints: Dict[str, Optional[str]]
    status: str
    subscription: str
    created_at: Optional[str]
    features: Dict[str, Any]


class ProvisioningLogOut(BaseModel):
    id: int
    workspace: int
    timestamp: datetime
    level: str
    message: str
    data: Dict[str, Any]
