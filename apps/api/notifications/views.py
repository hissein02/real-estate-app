from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsAdminRole

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(ListAPIView):
    """GET /notifications/ — paginated email log for admins."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = NotificationSerializer
    # Default page size; client can override with ?page_size=N (max 200)
    page_size = 50

    def get_queryset(self):
        qs = Notification.objects.select_related(
            "lease__tenant", "lease__unit"
        ).order_by("-created_at")

        # Optional filters
        ntype = self.request.query_params.get("type")
        if ntype:
            qs = qs.filter(notification_type=ntype)

        nstatus = self.request.query_params.get("status")
        if nstatus:
            qs = qs.filter(status=nstatus)

        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(recipient_email__icontains=search)
                | Q(subject__icontains=search)
                | Q(content__icontains=search)
                | Q(triggered_by__icontains=search)
            )

        return qs
