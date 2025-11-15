from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import MetaUser


@admin.register(MetaUser)
class MetaUserAdmin(BaseUserAdmin):
    """Admin configuration for MetaUser."""
    list_display = ('email', 'username', 'subscription_tier', 'max_workspaces', 'email_verified', 'created_at')
    list_filter = ('subscription_tier', 'email_verified', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Subscription', {'fields': ('subscription_tier', 'max_workspaces')}),
        ('Status', {'fields': ('email_verified', 'is_active', 'is_staff', 'is_superuser')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'last_login')}),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'subscription_tier'),
        }),
    )
