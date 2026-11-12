from rest_framework.routers import DefaultRouter

from .views import TenantViewSet, LeaseViewSet

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("leases", LeaseViewSet, basename="lease")

urlpatterns = router.urls
