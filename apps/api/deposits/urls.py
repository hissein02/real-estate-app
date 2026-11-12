from rest_framework.routers import DefaultRouter

from .views import DepositTransactionViewSet

router = DefaultRouter()
router.register("deposits", DepositTransactionViewSet, basename="deposit")

urlpatterns = router.urls
