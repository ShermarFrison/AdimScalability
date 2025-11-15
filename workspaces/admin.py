from django.contrib import admin
from .models import Workspace, WorkspaceOTP, ProvisioningLog


class WorkspaceOTPInline(admin.TabularInline):
    """Inline admin for workspace OTPs."""
    model = WorkspaceOTP
    extra = 0
    readonly_fields = ('otp_code', 'created_at', 'expires_at', 'used_at', 'usage_count', 'is_valid')
    fields = ('otp_code', 'is_active', 'max_uses', 'usage_count', 'is_valid', 'created_at', 'expires_at')


class ProvisioningLogInline(admin.TabularInline):
    """Inline admin for provisioning logs."""
    model = ProvisioningLog
    extra = 0
    readonly_fields = ('timestamp', 'level', 'message', 'data')
    fields = ('timestamp', 'level', 'message')
    can_delete = False
    max_num = 10


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    """Admin configuration for Workspace."""
    list_display = (
        'workspace_id', 'name', 'owner', 'deployment_type',
        'status', 'region', 'created_at', 'provisioned_at'
    )
    list_filter = ('deployment_type', 'status', 'region', 'subscription_tier')
    search_fields = ('workspace_id', 'name', 'owner__email')
    readonly_fields = ('workspace_id', 'created_at', 'updated_at', 'provisioned_at', 'get_ports')

    fieldsets = (
        ('Identity', {
            'fields': ('workspace_id', 'name', 'owner')
        }),
        ('Deployment', {
            'fields': ('deployment_type', 'status', 'region', 'droplet_id')
        }),
        ('Endpoints', {
            'fields': ('instance_url', 'tailscale_url', 'ip_address')
        }),
        ('Resources', {
            'fields': ('vcpu', 'ram_gb', 'storage_gb')
        }),
        ('Subscription', {
            'fields': ('subscription_tier', 'monthly_cost')
        }),
        ('Configuration', {
            'fields': ('config_data', 'get_ports'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'provisioned_at', 'decommissioned_at')
        }),
    )

    inlines = [WorkspaceOTPInline, ProvisioningLogInline]

    def get_ports(self, obj):
        """Display port allocation."""
        ports = obj.get_port_allocation()
        return ', '.join(f"{k}: {v}" for k, v in ports.items())
    get_ports.short_description = 'Port Allocation'


@admin.register(WorkspaceOTP)
class WorkspaceOTPAdmin(admin.ModelAdmin):
    """Admin configuration for WorkspaceOTP."""
    list_display = (
        'otp_code', 'workspace', 'is_active', 'is_valid',
        'usage_count', 'max_uses', 'created_at', 'expires_at'
    )
    list_filter = ('is_active', 'workspace__deployment_type')
    search_fields = ('otp_code', 'workspace__workspace_id', 'workspace__name')
    readonly_fields = ('otp_code', 'created_at', 'expires_at', 'used_at', 'usage_count', 'is_valid')

    fieldsets = (
        (None, {
            'fields': ('workspace', 'otp_code')
        }),
        ('Status', {
            'fields': ('is_active', 'is_valid', 'max_uses', 'usage_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'expires_at', 'used_at', 'last_used_ip')
        }),
    )


@admin.register(ProvisioningLog)
class ProvisioningLogAdmin(admin.ModelAdmin):
    """Admin configuration for ProvisioningLog."""
    list_display = ('workspace', 'level', 'message_preview', 'timestamp')
    list_filter = ('level', 'workspace__deployment_type', 'timestamp')
    search_fields = ('workspace__workspace_id', 'message')
    readonly_fields = ('workspace', 'timestamp', 'level', 'message', 'data')

    def message_preview(self, obj):
        """Show message preview."""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message'

    def has_add_permission(self, request):
        """Prevent manual creation of logs."""
        return False
