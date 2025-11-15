from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import MetaUser


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = MetaUser
        fields = ( 'email', 'username', 'password', 'password_confirm', 'subscription_tier')
        extra_kwargs = {
            'subscription_tier': {'read_only': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = MetaUser.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details."""
    workspace_count = serializers.SerializerMethodField()

    class Meta:
        model = MetaUser
        fields = (
            'id', 'email', 'username', 'subscription_tier',
            'max_workspaces', 'workspace_count', 'can_create_workspace',
            'email_verified', 'created_at'
        )
        read_only_fields = ('id', 'created_at', 'email_verified')

    def get_workspace_count(self, obj):
        return obj.workspaces.filter(status__in=['provisioning', 'active']).count()

