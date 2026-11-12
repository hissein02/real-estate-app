from rest_framework.routers import DefaultRouter

from .views import OwnerViewSet, PropertyViewSet, UnitViewSet

router = DefaultRouter()
router.register("owners", OwnerViewSet, basename="owner")
router.register("properties", PropertyViewSet, basename="property")
router.register("units", UnitViewSet, basename="unit")

urlpatterns = router.urls
