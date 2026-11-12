from django.urls import path

from .views import UserDetailView, UserListCreateView, UserSetPasswordView

urlpatterns = [
    path("users/", UserListCreateView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<int:pk>/set-password/", UserSetPasswordView.as_view(), name="user-set-password"),
]
