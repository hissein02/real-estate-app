from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source="actor.username", read_only=True, default="system"
    )

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_username", "action",
            "object_type", "object_id", "object_repr",
            "snapshot_json", "reason",
            "ip_address", "user_agent", "created_at",
        ]
