from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    VOID = "void", "Void"
    HARD_DELETE = "hard_delete", "Hard Delete"
    RENEW_LEASE = "renew_lease", "Renew Lease"
    TERMINATE_LEASE = "terminate_lease", "Terminate Lease"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=500, blank=True)
    snapshot_json = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self):
        actor_str = self.actor.username if self.actor else "system"
        return f"[{self.action}] {self.object_type}#{self.object_id} by {actor_str}"
