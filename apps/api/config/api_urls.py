from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from core.views import LoginView, LogoutView, MeView

urlpatterns = [
    # Auth
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    # Resources
    path("", include("core.urls")),
    path("", include("portfolio.urls")),
    path("", include("tenants.urls")),
    path("", include("billing.urls")),
    path("", include("deposits.urls")),
    path("", include("audit.urls")),
    path("", include("reports.urls")),
    path("", include("settings_app.urls")),
    path("", include("notifications.urls")),
]
