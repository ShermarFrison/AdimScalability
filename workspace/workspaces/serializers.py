from rest_framework import serializers
from .models import Workspace, WorkspaceOTP, ProvisioningLog


class WorkspaceSerializer(serializers.ModelSerializer):
    """Serializer for workspace details."""
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    port_allocation = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            'id', 'workspace_id', 'name', 'owner', 'owner_email',
            'deployment_type', 'status', 'instance_url', 'tailscale_url',
            'ip_address', 'droplet_id', 'region', 'vcpu', 'ram_gb',
            'storage_gb', 'subscription_tier', 'monthly_cost',
            'created_at', 'updated_at', 'provisioned_at',
            'config_data', 'port_allocation'
        )
        read_only_fields = (
            'id', 'workspace_id', 'owner', 'status', 'droplet_id',
            'created_at', 'updated_at', 'provisioned_at'
        )

    def get_port_allocation(self, obj):
        return obj.get_port_allocation()


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new workspace."""

    class Meta:
        model = Workspace
        fields = (
            'name', 'deployment_type', 'region',
            'vcpu', 'ram_gb', 'storage_gb'
        )

    def validate(self, attrs):
        # Validate user can create workspace
        user = self.context['request'].user
        if not user.can_create_workspace:
            raise serializers.ValidationError(
                "You have reached the maximum number of workspaces for your subscription tier."
            )
        return attrs

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class OTPSerializer(serializers.ModelSerializer):
    """Serializer for OTP details."""
    workspace_id = serializers.CharField(source='workspace.workspace_id', read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)

    class Meta:
        model = WorkspaceOTP
        fields = (
            'id', 'workspace', 'workspace_id', 'workspace_name',
            'otp_code', 'created_at', 'expires_at', 'used_at',
            'is_active', 'usage_count', 'max_uses', 'is_valid'
        )
        read_only_fields = (
            'id', 'otp_code', 'created_at', 'expires_at',
            'used_at', 'usage_count'
        )


class OTPValidationSerializer(serializers.Serializer):
    """Serializer for OTP validation request."""
    otp = serializers.CharField(max_length=12, required=True)

    def validate_otp(self, value):
        try:
            otp = WorkspaceOTP.objects.get(otp_code=value.upper())
            if not otp.is_valid:
                raise serializers.ValidationError("OTP is invalid or has expired.")
            return value.upper()
        except WorkspaceOTP.DoesNotExist:
            raise serializers.ValidationError("OTP not found.")


class ProvisioningLogSerializer(serializers.ModelSerializer):
    """Serializer for provisioning logs."""

    class Meta:
        model = ProvisioningLog
        fields = ('id', 'workspace', 'timestamp', 'level', 'message', 'data')
        read_only_fields = ('id', 'timestamp')
