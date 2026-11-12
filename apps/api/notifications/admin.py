from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["pk", "notification_type", "recipient_email", "status", "sent_at", "created_at"]
    list_filter = ["notification_type", "status"]
    search_fields = ["recipient_email", "subject"]
    raw_id_fields = ["lease"]
    date_hierarchy = "created_at"
