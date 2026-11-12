from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(
        source="get_notification_type_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    # Compact lease info so the frontend can show tenant/unit without extra fetches
    lease_info = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "lease",
            "lease_info",
            "notification_type",
            "type_display",
            "recipient_email",
            "subject",
            "content",
            "body",
            "triggered_by",
            "status",
            "status_display",
            "sent_at",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields

    def get_lease_info(self, obj):
        if not obj.lease_id:
            return None
        try:
            lease = obj.lease
            return {
                "id": lease.pk,
                "tenant_name": lease.tenant.display_name,
                "unit_name": lease.unit.name,
            }
        except Exception:
            return None
