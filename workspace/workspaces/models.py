import secrets
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def generate_workspace_id():
    """Generate unique workspace ID: ws + 5 random chars (e.g., ws7x2k)"""
    return 'ws' + secrets.token_hex(3)[:5]


def generate_otp():
    """Generate OTP: workspace-id-XXXXXX (6 digits)"""
    return secrets.token_hex(3).upper()


class Workspace(models.Model):
    """
    Represents a deployed ADIM workspace instance.
    Can be on DigitalOcean, bare metal, or other cloud providers.
    """
    STATUS_CHOICES = [
        ('provisioning', 'Provisioning'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('migrating', 'Migrating'),
        ('decommissioned', 'Decommissioned'),
        ('failed', 'Failed'),
    ]

    DEPLOYMENT_CHOICES = [
        ('cloud', 'Cloud (DigitalOcean)'),
        ('bare_metal', 'Bare Metal'),
        ('aws', 'AWS'),
        ('gcp', 'Google Cloud'),
        ('other', 'Other'),
    ]

    # Identity
    workspace_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_workspace_id,
        editable=False
    )
    name = models.CharField(max_length=100, help_text="Friendly name for the workspace")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspaces'
    )

    # Deployment
    deployment_type = models.CharField(max_length=20, choices=DEPLOYMENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='provisioning')

    # Connection endpoints
    instance_url = models.URLField(blank=True, help_text="Main HTTPS endpoint")
    tailscale_url = models.URLField(blank=True, help_text="Tailscale private endpoint")
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    # Cloud provider details (for cloud deployments)
    droplet_id = models.CharField(max_length=100, blank=True, help_text="DigitalOcean Droplet ID")
    region = models.CharField(max_length=50, blank=True, help_text="Datacenter region")

    # Resource specs
    vcpu = models.IntegerField(default=2, help_text="Virtual CPUs")
    ram_gb = models.IntegerField(default=4, help_text="RAM in GB")
    storage_gb = models.IntegerField(default=50, help_text="Storage in GB")

    # Subscription & billing
    subscription_tier = models.CharField(max_length=20, default='starter')
    monthly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    provisioned_at = models.DateTimeField(blank=True, null=True)
    decommissioned_at = models.DateTimeField(blank=True, null=True)

    # Configuration
    config_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional configuration (ports, features, etc.)"
    )

    class Meta:
        db_table = 'workspaces'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workspace_id']),
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f"{self.workspace_id} - {self.name} ({self.owner.email})"

    def mark_provisioned(self):
        """Mark workspace as successfully provisioned."""
        self.status = 'active'
        self.provisioned_at = timezone.now()
        self.save()

    def mark_failed(self):
        """Mark workspace provisioning as failed."""
        self.status = 'failed'
        self.save()

    def get_port_allocation(self):
        """Get unique port allocation for this workspace's services."""
        hash_value = int(hashlib.md5(self.workspace_id.encode()).hexdigest()[:6], 16)
        base_offset = (hash_value % 1000) * 10

        return {
            'daphne': 8000 + base_offset,
            'redis': 6379 + base_offset,
            'qdrant_http': 6333 + base_offset,
            'qdrant_grpc': 6334 + base_offset,
            'neo4j': 7687 + base_offset,
        }


class WorkspaceOTP(models.Model):
    """
    One-Time Passwords for workspace connection.
    Client apps use OTPs to discover and connect to workspaces.
    """
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='otps'
    )
    otp_code = models.CharField(
        max_length=12,
        unique=True,
        default=generate_otp,
        editable=False
    )

    # OTP lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # Usage tracking
    usage_count = models.IntegerField(default=0)
    max_uses = models.IntegerField(default=1, help_text="0 = unlimited")
    last_used_ip = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        db_table = 'workspace_otps'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['otp_code']),
            models.Index(fields=['workspace', 'is_active']),
        ]

    def __str__(self):
        return f"OTP {self.otp_code} for {self.workspace.workspace_id}"

    def save(self, *args, **kwargs):
        # Set expiration to 24 hours if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Check if OTP is valid for use."""
        if not self.is_active:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.max_uses > 0 and self.usage_count >= self.max_uses:
            return False
        if self.workspace.status not in ['active', 'provisioning']:
            return False
        return True

    def mark_used(self, ip_address=None):
        """Mark OTP as used."""
        self.usage_count += 1
        self.used_at = timezone.now()
        if ip_address:
            self.last_used_ip = ip_address

        # Deactivate if max uses reached
        if self.max_uses > 0 and self.usage_count >= self.max_uses:
            self.is_active = False

        self.save()

    def get_connection_details(self):
        """Get connection details for this OTP's workspace."""
        workspace = self.workspace
        return {
            'workspace_id': workspace.workspace_id,
            'name': workspace.name,
            'otp': self.otp_code,
            'endpoints': {
                'cloud': workspace.instance_url or None,
                'tailscale': workspace.tailscale_url or None,
                'ip': workspace.ip_address or None,
            },
            'status': workspace.status,
            'subscription': workspace.subscription_tier,
            'created_at': workspace.created_at.isoformat(),
            'features': workspace.config_data.get('features', {}),
        }


class ProvisioningLog(models.Model):
    """
    Tracks provisioning progress and logs for workspaces.
    """
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(
        max_length=10,
        choices=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        default='info'
    )
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'provisioning_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['workspace', '-timestamp']),
        ]

    def __str__(self):
        return f"[{self.level.upper()}] {self.workspace.workspace_id}: {self.message[:50]}"
