from django.contrib.auth.models import AbstractUser
from django.db import models


class MetaUser(AbstractUser):
    """
    Meta platform user - manages workspaces and subscriptions.
    NOT the same as workspace users.
    """
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    subscription_tier = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('starter', 'Starter'),
            ('pro', 'Pro'),
        ],
        default='free'
    )
    max_workspaces = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Override username requirement - use email instead
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'meta_users'
        verbose_name = 'Meta User'
        verbose_name_plural = 'Meta Users'

    def __str__(self):
        return f"{self.email} ({self.subscription_tier})"

    @property
    def can_create_workspace(self):
        """Check if user can create more workspaces based on subscription."""
        current_count = self.workspaces.filter(status__in=['provisioning', 'active']).count()
        return current_count < self.max_workspaces
